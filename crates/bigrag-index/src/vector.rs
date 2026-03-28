use bigrag_common::types::DistanceMetric;
use dashmap::DashMap;
use parking_lot::RwLock;
use std::collections::BinaryHeap;
use std::cmp::Ordering;
use std::sync::Arc;

/// SPFresh-based vector index with incremental rebalancing.
///
/// Vectors are clustered into posting lists. Each cluster has a centroid.
/// Queries find nearest centroids, then search within those posting lists.
pub struct VectorIndex {
    /// Centroid vectors for each cluster.
    centroids: RwLock<Vec<Centroid>>,
    /// Posting lists: cluster_id -> list of (vector_id, vector).
    postings: DashMap<u32, Vec<PostingEntry>>,
    /// Distance metric.
    metric: DistanceMetric,
    /// Vector dimensionality.
    dims: u32,
    /// Number of posting lists to probe during search.
    nprobe: usize,
}

#[derive(Debug, Clone)]
struct Centroid {
    id: u32,
    vector: Vec<f32>,
}

#[derive(Debug, Clone)]
pub struct PostingEntry {
    pub id: u64,
    pub vector: Vec<f32>,
}

#[derive(Debug, Clone)]
pub struct SearchResult {
    pub id: u64,
    pub distance: f32,
}

impl Eq for SearchResult {}
impl PartialEq for SearchResult {
    fn eq(&self, other: &Self) -> bool {
        self.id == other.id
    }
}
impl PartialOrd for SearchResult {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
impl Ord for SearchResult {
    fn cmp(&self, other: &Self) -> Ordering {
        // Max-heap: larger distance = lower priority (we want smallest distances)
        self.distance.partial_cmp(&other.distance).unwrap_or(Ordering::Equal)
    }
}

impl VectorIndex {
    pub fn new(dims: u32, metric: DistanceMetric) -> Self {
        Self {
            centroids: RwLock::new(Vec::new()),
            postings: DashMap::new(),
            metric,
            dims,
            nprobe: 64,
        }
    }

    pub fn with_nprobe(mut self, nprobe: usize) -> Self {
        self.nprobe = nprobe;
        self
    }

    /// Insert a vector into the index.
    pub fn insert(&self, id: u64, vector: Vec<f32>) {
        let centroids = self.centroids.read();
        if centroids.is_empty() {
            // No clusters yet — create the first one with this vector as centroid
            drop(centroids);
            let mut centroids = self.centroids.write();
            let cluster_id = centroids.len() as u32;
            centroids.push(Centroid {
                id: cluster_id,
                vector: vector.clone(),
            });
            self.postings.insert(
                cluster_id,
                vec![PostingEntry {
                    id,
                    vector,
                }],
            );
            return;
        }

        // Find nearest centroid
        let nearest = self.find_nearest_centroid(&vector, &centroids);
        drop(centroids);

        // Append to that posting list
        let mut posting = self.postings.entry(nearest).or_default();
        posting.push(PostingEntry { id, vector });

        // Check if split is needed (posting too large)
        let len = posting.len();
        drop(posting);
        if len > 1000 {
            self.maybe_split(nearest);
        }
    }

    /// Delete a vector by ID.
    pub fn delete(&self, id: u64) {
        for mut posting in self.postings.iter_mut() {
            posting.value_mut().retain(|e| e.id != id);
        }
    }

    /// ANN search: find top_k nearest neighbors.
    pub fn search_ann(&self, query: &[f32], top_k: usize) -> Vec<SearchResult> {
        let centroids = self.centroids.read();
        if centroids.is_empty() {
            return vec![];
        }

        // Find nearest centroids to probe
        let probe_clusters = self.find_nearest_centroids(query, &centroids, self.nprobe);
        drop(centroids);

        // Search within those posting lists
        let mut heap: BinaryHeap<SearchResult> = BinaryHeap::new();

        for cluster_id in probe_clusters {
            if let Some(posting) = self.postings.get(&cluster_id) {
                for entry in posting.value() {
                    let dist = self.compute_distance(query, &entry.vector);
                    if dist == 0.0 {
                        continue; // Skip zero-distance (the query itself)
                    }

                    if heap.len() < top_k {
                        heap.push(SearchResult {
                            id: entry.id,
                            distance: dist,
                        });
                    } else if let Some(worst) = heap.peek() {
                        if dist < worst.distance {
                            heap.pop();
                            heap.push(SearchResult {
                                id: entry.id,
                                distance: dist,
                            });
                        }
                    }
                }
            }
        }

        let mut results: Vec<SearchResult> = heap.into_sorted_vec();
        results.reverse(); // Sort ascending by distance
        results
    }

    /// Exact kNN search: scan all vectors.
    pub fn search_knn(&self, query: &[f32], top_k: usize) -> Vec<SearchResult> {
        let mut heap: BinaryHeap<SearchResult> = BinaryHeap::new();

        for posting in self.postings.iter() {
            for entry in posting.value() {
                let dist = self.compute_distance(query, &entry.vector);
                if dist == 0.0 {
                    continue;
                }

                if heap.len() < top_k {
                    heap.push(SearchResult {
                        id: entry.id,
                        distance: dist,
                    });
                } else if let Some(worst) = heap.peek() {
                    if dist < worst.distance {
                        heap.pop();
                        heap.push(SearchResult {
                            id: entry.id,
                            distance: dist,
                        });
                    }
                }
            }
        }

        let mut results: Vec<SearchResult> = heap.into_sorted_vec();
        results.reverse();
        results
    }

    /// Total number of vectors in the index.
    pub fn len(&self) -> usize {
        self.postings.iter().map(|p| p.value().len()).sum()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    fn find_nearest_centroid(&self, query: &[f32], centroids: &[Centroid]) -> u32 {
        let mut best_id = 0;
        let mut best_dist = f32::MAX;
        for c in centroids {
            let dist = self.compute_distance(query, &c.vector);
            if dist < best_dist {
                best_dist = dist;
                best_id = c.id;
            }
        }
        best_id
    }

    fn find_nearest_centroids(&self, query: &[f32], centroids: &[Centroid], n: usize) -> Vec<u32> {
        let mut dists: Vec<(u32, f32)> = centroids
            .iter()
            .map(|c| (c.id, self.compute_distance(query, &c.vector)))
            .collect();
        dists.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(Ordering::Equal));
        dists.into_iter().take(n).map(|(id, _)| id).collect()
    }

    fn compute_distance(&self, a: &[f32], b: &[f32]) -> f32 {
        match self.metric {
            DistanceMetric::CosineDistance => cosine_distance(a, b),
            DistanceMetric::EuclideanSquared => euclidean_squared(a, b),
        }
    }

    fn maybe_split(&self, cluster_id: u32) {
        // Simple split: divide posting list in half, create new centroid
        let posting = match self.postings.get(&cluster_id) {
            Some(p) => p.value().clone(),
            None => return,
        };

        if posting.len() <= 500 {
            return;
        }

        let mid = posting.len() / 2;
        let (left, right) = posting.split_at(mid);

        // Compute new centroid for right half
        let new_centroid = compute_mean_vector(right);

        let mut centroids = self.centroids.write();
        let new_id = centroids.len() as u32;
        centroids.push(Centroid {
            id: new_id,
            vector: new_centroid,
        });

        // Update posting lists
        self.postings.insert(cluster_id, left.to_vec());
        self.postings.insert(new_id, right.to_vec());
    }
}

fn cosine_distance(a: &[f32], b: &[f32]) -> f32 {
    let mut dot = 0.0f32;
    let mut norm_a = 0.0f32;
    let mut norm_b = 0.0f32;

    for i in 0..a.len().min(b.len()) {
        dot += a[i] * b[i];
        norm_a += a[i] * a[i];
        norm_b += b[i] * b[i];
    }

    let denom = norm_a.sqrt() * norm_b.sqrt();
    if denom == 0.0 {
        return 2.0; // Maximum distance
    }

    1.0 - (dot / denom)
}

fn euclidean_squared(a: &[f32], b: &[f32]) -> f32 {
    let mut sum = 0.0f32;
    for i in 0..a.len().min(b.len()) {
        let diff = a[i] - b[i];
        sum += diff * diff;
    }
    sum
}

fn compute_mean_vector(entries: &[PostingEntry]) -> Vec<f32> {
    if entries.is_empty() {
        return vec![];
    }
    let dims = entries[0].vector.len();
    let mut mean = vec![0.0f32; dims];
    for entry in entries {
        for (i, &v) in entry.vector.iter().enumerate() {
            mean[i] += v;
        }
    }
    let n = entries.len() as f32;
    for v in &mut mean {
        *v /= n;
    }
    mean
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vector_index_insert_and_search() {
        let idx = VectorIndex::new(3, DistanceMetric::EuclideanSquared);

        idx.insert(1, vec![1.0, 0.0, 0.0]);
        idx.insert(2, vec![0.0, 1.0, 0.0]);
        idx.insert(3, vec![0.0, 0.0, 1.0]);
        idx.insert(4, vec![1.0, 1.0, 0.0]);

        let results = idx.search_knn(&[1.0, 0.1, 0.0], 2);
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].id, 1); // Closest to [1,0,0]
    }

    #[test]
    fn test_cosine_distance() {
        let d = cosine_distance(&[1.0, 0.0], &[1.0, 0.0]);
        assert!((d - 0.0).abs() < 1e-6);

        let d = cosine_distance(&[1.0, 0.0], &[0.0, 1.0]);
        assert!((d - 1.0).abs() < 1e-6);
    }

    #[test]
    fn test_euclidean_squared() {
        let d = euclidean_squared(&[0.0, 0.0], &[3.0, 4.0]);
        assert!((d - 25.0).abs() < 1e-6);
    }

    #[test]
    fn test_delete() {
        let idx = VectorIndex::new(2, DistanceMetric::EuclideanSquared);
        idx.insert(1, vec![1.0, 0.0]);
        idx.insert(2, vec![0.0, 1.0]);

        assert_eq!(idx.len(), 2);
        idx.delete(1);
        assert_eq!(idx.len(), 1);
    }
}
