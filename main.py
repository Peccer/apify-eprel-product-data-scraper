import asyncio
from typing import Dict, Any, List
from urllib.parse import urljoin
from datetime import datetime, timezone

from playwright.async_api import async_playwright, Page, Locator
from apify import Actor

async def main():
    async with Actor:
        # 1. Initialize input
        actor_input = await Actor.get_input() or {}
        # Default to washing machines as per your logs, but works for other categories too
        start_urls = actor_input.get("startUrls", [{"url": "https://eprel.ec.europa.eu/screen/product/washingmachines2019"}])
        max_results = actor_input.get("maxResults", 100)

        Actor.log.info(f"Starting EPREL Visual Scraper for {len(start_urls)} URLs.")

        actor_env = Actor.get_env()

        async with async_playwright() as p:
            # 2. Setup browser
            browser = await p.chromium.launch(
                headless=actor_env.get('headless', True),
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            
            # Create context with a standard user agent to avoid bot detection
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            scraped_count = 0

            for start_url_obj in start_urls:
                if scraped_count >= max_results:
                    break

                url = start_url_obj.get("url")
                Actor.log.info(f"Processing URL: {url}")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # 3. Wait for the Angular App to load the cards
                    # We wait for the card container component found in your HTML
                    try:
                        await page.wait_for_selector("app-search-result-card", timeout=30000)
                    except Exception:
                        Actor.log.warning(f"No product cards found at {url}")
                        continue

                    # 4. Scrape the current page until max_results is reached
                    while scraped_count < max_results:
                        # Get all product cards visible on the current page
                        cards = await page.locator("app-search-result-card").all()
                        Actor.log.info(f"Found {len(cards)} cards on current page.")

                        for card in cards:
                            if scraped_count >= max_results:
                                break
                            
                            # Extract data from the card using the helper function
                            product_data = await extract_card_data(card, page.url)
                            
                            if product_data:
                                await Actor.push_data(product_data)
                                scraped_count += 1
                        
                        if scraped_count >= max_results:
                            break

                        # 5. Handle Pagination (Click 'Next')
                        # Selector based on HTML: <ecl-pagination-item class="...--next"> <a ...>
                        next_btn = page.locator(".ecl-pagination__item--next a").first
                        
                        if await next_btn.count() > 0 and await next_btn.is_visible():
                            Actor.log.info("Navigating to next page...")
                            await next_btn.click()
                            # Wait for the list to refresh (waiting for a card to be attached again is a simple check)
                            await page.wait_for_timeout(2000) # Small buffer for Angular animation
                            await page.wait_for_selector("app-search-result-card", timeout=30000)
                        else:
                            Actor.log.info("No next page button found. Stopping pagination.")
                            break

                except Exception as e:
                    Actor.log.error(f"Failed to process {url}: {str(e)}")

            await browser.close()
            Actor.log.info(f"Scraping finished. Total items: {scraped_count}")

async def extract_card_data(card: Locator, current_url: str) -> Dict[str, Any]:
    """
    Extracts details directly from the listing card (Visual Scraping).
    This matches the specific Angular HTML structure provided.
    """
    try:
        # -- Brand --
        # HTML: <eui-card-header-title ...> <span> AEG </span> ...
        brand = await card.locator("eui-card-header-title").first.inner_text()
        
        # -- Model Identifier --
        # HTML: <eui-card-header-subtitle ...> LFED61844B... </eui-card-header-subtitle>
        model_id = await card.locator("eui-card-header-subtitle").first.inner_text()
        
        # -- Energy Class --
        # HTML: <app-energy-thumbnail> <img title="Energieklasse A" ...>
        energy_class = "N/A"
        img_locator = card.locator("app-energy-thumbnail img").first
        if await img_locator.count() > 0:
            # The class is usually in the 'title' attribute, e.g. "Energieklasse A"
            title_attr = await img_locator.get_attribute("title")
            if title_attr:
                # Clean string: "Energieklasse A" -> "A"
                energy_class = title_attr.replace("Energieklasse", "").replace("Energy class", "").strip()

        # -- Technical Specifications --
        # HTML: <app-parameter-item-new> contains <dt> (key) and <dd> (value)
        specs = {}
        param_rows = await card.locator("app-parameter-item-new").all()
        
        for row in param_rows:
            key_loc = row.locator("dt")
            val_loc = row.locator("dd")
            
            if await key_loc.count() > 0 and await val_loc.count() > 0:
                key_text = (await key_loc.inner_text()).strip()
                val_text = (await val_loc.inner_text()).strip()
                # Clean up newlines in values (e.g., "85 x 60\n cm" -> "85 x 60 cm")
                val_text = " ".join(val_text.split())
                if key_text:
                    specs[key_text] = val_text

        # Generate a direct URL if possible (EPREL URLs usually follow a pattern)
        # We try to infer it from the context or the inputs, but strictly scraping, 
        # the card usually has a 'More details' button.
        # We return the current listing URL as 'source_url' for reference.
        
        actor_env = Actor.get_env()
        scraped_at = actor_env.started_at.isoformat() if actor_env.started_at else datetime.now(timezone.utc).isoformat()

        return {
            "brand": brand.strip(),
            "modelIdentifier": model_id.strip(),
            "energyClass": energy_class,
            "specifications": specs,
            "scrapedAt": scraped_at,
            "sourceUrl": current_url
        }

    except Exception as e:
        # Log warning but don't crash the scraper
        # await Actor.log.warning(f"Error extracting card: {e}") # Uncomment for verbose debug
        return None

if __name__ == "__main__":
    asyncio.run(main())