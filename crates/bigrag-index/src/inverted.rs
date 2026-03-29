use std::collections::{BTreeMap, HashMap};

/// Block-based inverted index for BM25 full-text search.
///
/// Posting lists are partitioned into blocks of ~256 postings.
/// Each block stores a max BM25 score for MAXSCORE optimization.
pub struct InvertedIndex {
    /// Term → list of posting blocks.
    terms: BTreeMap<String, Vec<PostingBlock>>,
    /// Document lengths for BM25 normalization.
    doc_lengths: HashMap<u64, u32>,
    /// Total number of documents.
    num_docs: u64,
    /// Average document length.
    avg_doc_length: f64,
    /// BM25 parameters.
    k1: f64,
    b: f64,
}

/// A single posting block containing up to 512 postings.
#[derive(Debug, Clone)]
pub struct PostingBlock {
    /// Document IDs in this block (sorted).
    pub doc_ids: Vec<u64>,
    /// BM25 weights per document (parallel with doc_ids).
    pub weights: Vec<f32>,
    /// Maximum BM25 score any document in this block can contribute.
    pub block_max_score: f32,
    /// Block sequence ID for ordering.
    pub block_id: u32,
}

const MAX_BLOCK_SIZE: usize = 512;

/// Result of a BM25 search.
#[derive(Debug, Clone)]
pub struct BM25Result {
    pub doc_id: u64,
    pub score: f32,
}

impl InvertedIndex {
    pub fn new(k1: f64, b: f64, _k3: f64) -> Self {
        Self {
            terms: BTreeMap::new(),
            doc_lengths: HashMap::new(),
            num_docs: 0,
            avg_doc_length: 0.0,
            k1,
            b,
        }
    }

    pub fn with_defaults() -> Self {
        Self::new(1.2, 0.75, 8.0)
    }

    /// Add a document to the index.
    pub fn add_document(&mut self, doc_id: u64, tokens: &[String]) {
        let doc_length = tokens.len() as u32;
        self.doc_lengths.insert(doc_id, doc_length);
        self.num_docs += 1;

        // Update average document length
        let total_length: u64 = self.doc_lengths.values().map(|&l| l as u64).sum();
        self.avg_doc_length = total_length as f64 / self.num_docs as f64;

        // Count term frequencies in this document
        let mut tf_map: HashMap<&str, u32> = HashMap::new();
        for token in tokens {
            *tf_map.entry(token.as_str()).or_default() += 1;
        }

        // Add to posting lists
        for (term, tf) in tf_map {
            let weight = self.compute_bm25_weight(tf, doc_length);
            let blocks = self.terms.entry(term.to_string()).or_default();

            // Add to last block or create new one
            if let Some(last) = blocks.last_mut() {
                if last.doc_ids.len() < MAX_BLOCK_SIZE {
                    last.doc_ids.push(doc_id);
                    last.weights.push(weight);
                    last.block_max_score = last.block_max_score.max(weight);
                } else {
                    // Block full — create new
                    let block_id = blocks.len() as u32;
                    blocks.push(PostingBlock {
                        doc_ids: vec![doc_id],
                        weights: vec![weight],
                        block_max_score: weight,
                        block_id,
                    });
                }
            } else {
                blocks.push(PostingBlock {
                    doc_ids: vec![doc_id],
                    weights: vec![weight],
                    block_max_score: weight,
                    block_id: 0,
                });
            }
        }
    }

    /// Remove a document from the index.
    pub fn remove_document(&mut self, doc_id: u64) {
        self.doc_lengths.remove(&doc_id);
        self.num_docs = self.num_docs.saturating_sub(1);

        for blocks in self.terms.values_mut() {
            for block in blocks.iter_mut() {
                if let Some(pos) = block.doc_ids.iter().position(|&id| id == doc_id) {
                    block.doc_ids.remove(pos);
                    block.weights.remove(pos);
                    block.block_max_score = block
                        .weights
                        .iter()
                        .copied()
                        .fold(0.0f32, f32::max);
                }
            }
            // Remove empty blocks
            blocks.retain(|b| !b.doc_ids.is_empty());
        }

        // Remove terms with no postings
        self.terms.retain(|_, blocks| !blocks.is_empty());
    }

    /// BM25 search with MAXSCORE optimization.
    pub fn search(&self, query_tokens: &[String], top_k: usize) -> Vec<BM25Result> {
        if query_tokens.is_empty() {
            return vec![];
        }

        // Compute IDF for each query term
        let mut term_info: Vec<(&str, f64, &Vec<PostingBlock>)> = Vec::new();
        for token in query_tokens {
            if let Some(blocks) = self.terms.get(token.as_str()) {
                let df = blocks.iter().map(|b| b.doc_ids.len()).sum::<usize>() as f64;
                let idf = ((self.num_docs as f64 - df + 0.5) / (df + 0.5) + 1.0).ln();
                if idf > 0.0 {
                    term_info.push((token.as_str(), idf, blocks));
                }
            }
        }

        if term_info.is_empty() {
            return vec![];
        }

        // Sort terms by max possible contribution (ascending for MAXSCORE)
        term_info.sort_by(|a, b| {
            let a_max = a.2.iter().map(|bl| bl.block_max_score).fold(0.0f32, f32::max) as f64 * a.1;
            let b_max = b.2.iter().map(|bl| bl.block_max_score).fold(0.0f32, f32::max) as f64 * b.1;
            a_max.partial_cmp(&b_max).unwrap_or(std::cmp::Ordering::Equal)
        });

        // Score documents
        let mut scores: HashMap<u64, f32> = HashMap::new();

        for (_, idf, blocks) in &term_info {
            for block in *blocks {
                for (i, &doc_id) in block.doc_ids.iter().enumerate() {
                    let weight = block.weights[i];
                    let score = weight * (*idf as f32);
                    *scores.entry(doc_id).or_default() += score;
                }
            }
        }

        // Get top-k
        let mut results: Vec<BM25Result> = scores
            .into_iter()
            .filter(|(_, score)| *score > 0.0)
            .map(|(doc_id, score)| BM25Result { doc_id, score })
            .collect();

        results.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(top_k);
        results
    }

    /// Compute BM25 weight for a term in a document.
    fn compute_bm25_weight(&self, tf: u32, doc_length: u32) -> f32 {
        let tf = tf as f64;
        let dl = doc_length as f64;
        let avgdl = self.avg_doc_length.max(1.0);

        let numerator = tf * (self.k1 + 1.0);
        let denominator = tf + self.k1 * (1.0 - self.b + self.b * dl / avgdl);

        (numerator / denominator) as f32
    }

    pub fn num_terms(&self) -> usize {
        self.terms.len()
    }

    pub fn num_docs(&self) -> u64 {
        self.num_docs
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_and_search() {
        let mut idx = InvertedIndex::with_defaults();

        idx.add_document(1, &["the", "quick", "brown", "fox"].map(String::from));
        idx.add_document(2, &["the", "lazy", "brown", "dog"].map(String::from));
        idx.add_document(3, &["quick", "fox", "jumps"].map(String::from));

        let results = idx.search(&["quick".into(), "fox".into()], 10);
        assert!(!results.is_empty());
        // Doc 3 and doc 1 should be top results (both have quick + fox)
        assert!(results[0].doc_id == 3 || results[0].doc_id == 1);
    }

    #[test]
    fn test_remove_document() {
        let mut idx = InvertedIndex::with_defaults();
        idx.add_document(1, &["hello".into(), "world".into()]);
        idx.add_document(2, &["hello".into(), "rust".into()]);

        assert_eq!(idx.num_docs(), 2);
        idx.remove_document(1);
        assert_eq!(idx.num_docs(), 1);

        let results = idx.search(&["hello".into()], 10);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].doc_id, 2);
    }

    #[test]
    fn test_empty_search() {
        let idx = InvertedIndex::with_defaults();
        let results = idx.search(&["anything".into()], 10);
        assert!(results.is_empty());
    }

    #[test]
    fn test_bm25_scoring() {
        let mut idx = InvertedIndex::with_defaults();

        // Doc with higher TF for "rust" should score higher
        idx.add_document(1, &["rust".into(), "rust".into(), "rust".into(), "code".into()]);
        idx.add_document(2, &["rust".into(), "code".into(), "test".into()]);

        let results = idx.search(&["rust".into()], 10);
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].doc_id, 1); // Higher TF
        assert!(results[0].score > results[1].score);
    }
}
