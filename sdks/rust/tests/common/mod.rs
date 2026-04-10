use bigrag::BigRag;
use wiremock::MockServer;

pub async fn test_client(mock_server: &MockServer) -> BigRag {
    BigRag::builder()
        .base_url(&mock_server.uri())
        .api_key("test-key")
        .build()
        .unwrap()
}
