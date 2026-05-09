use std::time::Duration;

use reqwest::{Client, Method};
use serde::de::DeserializeOwned;
use serde::Serialize;

use crate::error::{parse_error_response, BigRagError};

/// Internal HTTP transport layer.
pub(crate) struct Transport {
    http: Client,
    pub(crate) base_url: String,
    api_key: Option<String>,
    timeout: Duration,
    max_retries: u32,
}

impl Transport {
    /// Create a new transport.
    pub fn new(
        base_url: &str,
        api_key: Option<String>,
        timeout: Duration,
        max_retries: u32,
    ) -> Self {
        let ua = format!("bigrag-rust/{}", env!("CARGO_PKG_VERSION"));
        let http = Client::builder()
            .user_agent(ua)
            .timeout(timeout)
            .build()
            .expect("failed to build reqwest client");

        Self {
            http,
            base_url: base_url.trim_end_matches('/').to_string(),
            api_key,
            timeout,
            max_retries,
        }
    }

    /// Create a transport with a user-provided reqwest client.
    pub fn with_client(
        http: Client,
        base_url: &str,
        api_key: Option<String>,
        timeout: Duration,
        max_retries: u32,
    ) -> Self {
        Self {
            http,
            base_url: base_url.trim_end_matches('/').to_string(),
            api_key,
            timeout,
            max_retries,
        }
    }

    /// GET request with optional query parameters.
    pub async fn get<T: DeserializeOwned>(
        &self,
        path: &str,
        query: Vec<(String, String)>,
    ) -> Result<T, BigRagError> {
        self.request_with_retry(Method::GET, path, None::<&()>, query)
            .await
    }

    /// POST request with a JSON body.
    pub async fn post<B: Serialize, T: DeserializeOwned>(
        &self,
        path: &str,
        body: &B,
    ) -> Result<T, BigRagError> {
        self.request_with_retry(Method::POST, path, Some(body), vec![])
            .await
    }

    /// PUT request with a JSON body.
    pub async fn put<B: Serialize, T: DeserializeOwned>(
        &self,
        path: &str,
        body: &B,
    ) -> Result<T, BigRagError> {
        self.request_with_retry(Method::PUT, path, Some(body), vec![])
            .await
    }

    /// PATCH request with a JSON body.
    pub async fn patch<B: Serialize, T: DeserializeOwned>(
        &self,
        path: &str,
        body: &B,
    ) -> Result<T, BigRagError> {
        self.request_with_retry(Method::PATCH, path, Some(body), vec![])
            .await
    }

    /// DELETE request.
    pub async fn delete<T: DeserializeOwned>(&self, path: &str) -> Result<T, BigRagError> {
        self.request_with_retry(Method::DELETE, path, None::<&()>, vec![])
            .await
    }

    /// POST multipart form-data (for file uploads). Not retried.
    pub async fn post_multipart<T: DeserializeOwned>(
        &self,
        path: &str,
        form: reqwest::multipart::Form,
    ) -> Result<T, BigRagError> {
        let url = format!("{}{}", self.base_url, path);
        let mut req = self.http.post(&url).multipart(form);
        if let Some(key) = &self.api_key {
            req = req.bearer_auth(key);
        }

        let response = req.send().await.map_err(|e| {
            if e.is_timeout() {
                BigRagError::Timeout(self.timeout)
            } else {
                BigRagError::Connection(e.to_string())
            }
        })?;

        if response.status().is_success() {
            response.json().await.map_err(|e| BigRagError::Api {
                status: 0,
                message: format!("response deserialization failed: {}", e),
            })
        } else {
            Err(parse_error_response(response).await)
        }
    }

    /// GET request that returns the raw response for SSE streaming. Not retried.
    pub async fn get_stream(&self, path: &str) -> Result<reqwest::Response, BigRagError> {
        let url = format!("{}{}", self.base_url, path);
        let mut req = self.http.get(&url);
        if let Some(key) = &self.api_key {
            req = req.bearer_auth(key);
        }

        let response = req.send().await.map_err(|e| {
            if e.is_timeout() {
                BigRagError::Timeout(self.timeout)
            } else {
                BigRagError::Connection(e.to_string())
            }
        })?;

        if response.status().is_success() {
            Ok(response)
        } else {
            Err(parse_error_response(response).await)
        }
    }

    async fn request_with_retry<B: Serialize, T: DeserializeOwned>(
        &self,
        method: Method,
        path: &str,
        body: Option<&B>,
        query: Vec<(String, String)>,
    ) -> Result<T, BigRagError> {
        let mut last_err = None;

        for attempt in 0..=self.max_retries {
            if attempt > 0 {
                let delay =
                    Duration::from_millis(500 * 2u64.pow(attempt - 1)).min(Duration::from_secs(4));
                tokio::time::sleep(delay).await;
            }

            match self.do_request::<B, T>(&method, path, body, &query).await {
                Ok(val) => return Ok(val),
                Err(e) if e.is_retryable() && attempt < self.max_retries => {
                    last_err = Some(e);
                }
                Err(e) => return Err(e),
            }
        }

        Err(last_err.unwrap())
    }

    async fn do_request<B: Serialize, T: DeserializeOwned>(
        &self,
        method: &Method,
        path: &str,
        body: Option<&B>,
        query: &[(String, String)],
    ) -> Result<T, BigRagError> {
        let url = format!("{}{}", self.base_url, path);
        let mut req = self.http.request(method.clone(), &url);

        if let Some(key) = &self.api_key {
            req = req.bearer_auth(key);
        }

        if !query.is_empty() {
            req = req.query(query);
        }

        if let Some(body) = body {
            req = req.json(body);
        }

        let response = req.send().await.map_err(|e| {
            if e.is_timeout() {
                BigRagError::Timeout(self.timeout)
            } else {
                BigRagError::Connection(e.to_string())
            }
        })?;

        if response.status().is_success() {
            response.json().await.map_err(|e| BigRagError::Api {
                status: 0,
                message: format!("response deserialization failed: {}", e),
            })
        } else {
            Err(parse_error_response(response).await)
        }
    }
}

/// Percent-encode a string for use in URL path segments or query parameters.
pub(crate) fn urlencode(s: &str) -> String {
    s.bytes()
        .map(|b| match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                String::from(b as char)
            }
            _ => format!("%{:02X}", b),
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use httpmock::Method::{GET, POST};
    use httpmock::MockServer;
    use serde_json::{json, Value};

    use super::{urlencode, Transport};
    use crate::error::BigRagError;

    #[tokio::test]
    async fn sends_auth_query_and_json_body() {
        let server = MockServer::start_async().await;
        let mock = server
            .mock_async(|when, then| {
                when.method(POST)
                    .path("/v1/collections")
                    .query_param("dry_run", "true")
                    .header("authorization", "Bearer bigrag_sk_test")
                    .json_body(json!({"name": "docs"}));
                then.status(200).json_body(json!({"id": "col"}));
            })
            .await;
        let transport = Transport::new(
            &server.base_url(),
            Some("bigrag_sk_test".to_string()),
            Duration::from_secs(5),
            0,
        );

        let result: Value = transport
            .request_with_retry(
                reqwest::Method::POST,
                "/v1/collections",
                Some(&json!({"name": "docs"})),
                vec![("dry_run".to_string(), "true".to_string())],
            )
            .await
            .unwrap();

        assert_eq!(result, json!({"id": "col"}));
        mock.assert_hits_async(1).await;
    }

    #[tokio::test]
    async fn retries_server_errors() {
        let server = MockServer::start_async().await;
        let mock = server
            .mock_async(|when, then| {
                when.method(GET).path("/health");
                then.status(503).json_body(json!({"detail": "temporary"}));
            })
            .await;
        let transport = Transport::new(&server.base_url(), None, Duration::from_secs(5), 1);

        let error = transport.get::<Value>("/health", vec![]).await.unwrap_err();

        assert!(matches!(error, BigRagError::ServerError { message, status: 503 } if message == "temporary"));
        mock.assert_hits_async(2).await;
    }

    #[tokio::test]
    async fn maps_error_statuses() {
        let server = MockServer::start_async().await;
        server
            .mock_async(|when, then| {
                when.method(GET).path("/missing");
                then.status(404).json_body(json!({"detail": "Missing"}));
            })
            .await;
        let transport = Transport::new(&server.base_url(), None, Duration::from_secs(5), 0);

        let error = transport.get::<Value>("/missing", vec![]).await.unwrap_err();

        assert!(matches!(error, BigRagError::NotFound { message } if message == "Missing"));
    }

    #[test]
    fn urlencodes_path_segments() {
        assert_eq!(urlencode("team docs/doc 1"), "team%20docs%2Fdoc%201");
    }
}
