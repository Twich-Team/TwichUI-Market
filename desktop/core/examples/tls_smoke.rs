//! Explicitly validates local certificate trust without disabling TLS verification.
use twichui_market_core::client::MarketClient;
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = MarketClient::new(
        &std::env::var("MARKET_TEST_SERVER")?,
        std::env::var("MARKET_TEST_TOKEN")?,
    )?;
    let result = client.authenticate();
    if std::env::var("MARKET_EXPECT_UNTRUSTED").as_deref() == Ok("true") {
        assert!(result.is_err(), "Untrusted local certificate was accepted");
    } else {
        result?;
    }
    Ok(())
}
