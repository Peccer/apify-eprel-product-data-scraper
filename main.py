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
        # Default to washing machines
        start_urls = actor_input.get("startUrls", [{"url": "https://eprel.ec.europa.eu/screen/product/washingmachines2019"}])
        
        # Force maxResults to be an integer
        max_results = int(actor_input.get("maxResults", 50))

        Actor.log.info(f"Starting EPREL Visual Scraper. Target: {max_results} items.")

        actor_env = Actor.get_env()

        async with async_playwright() as p:
            # 2. Setup browser
            browser = await p.chromium.launch(
                headless=actor_env.get('headless', True),
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            
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
                    try:
                        await page.wait_for_selector("app-search-result-card", timeout=30000)
                        # Small extra wait to ensure text content inside cards is hydrated
                        await page.wait_for_timeout(2000) 
                    except Exception:
                        Actor.log.warning(f"No product cards found at {url}")
                        continue

                    # 4. Scrape loop
                    while scraped_count < max_results:
                        # Get all product cards visible on the current page
                        cards = await page.locator("app-search-result-card").all()
                        Actor.log.info(f"Found {len(cards)} cards on current page.")

                        for i, card in enumerate(cards):
                            if scraped_count >= max_results:
                                Actor.log.info(f"Reached max results ({max_results}). Stopping.")
                                break
                            
                            # Extract data
                            product_data = await extract_card_data(card, page.url)
                            
                            if product_data:
                                await Actor.push_data(product_data)
                                scraped_count += 1
                                if scraped_count % 5 == 0:
                                    Actor.log.info(f"Progress: {scraped_count}/{max_results} items scraped.")
                            else:
                                Actor.log.warning(f"Failed to extract card {i} on this page.")
                        
                        if scraped_count >= max_results:
                            break

                        # 5. Handle Pagination
                        next_btn = page.locator(".ecl-pagination__item--next a").first
                        
                        if await next_btn.count() > 0 and await next_btn.is_visible():
                            Actor.log.info(f"Navigating to next page... (Currently scraped: {scraped_count})")
                            await next_btn.click()
                            
                            # Wait for list refresh
                            await page.wait_for_timeout(3000)
                            await page.wait_for_selector("app-search-result-card", timeout=30000)
                        else:
                            Actor.log.info("No next page button found or end of list. Stopping.")
                            break

                except Exception as e:
                    Actor.log.error(f"Failed to process {url}: {str(e)}")

            await browser.close()
            Actor.log.info(f"Scraping finished. Total items: {scraped_count}")

async def extract_card_data(card: Locator, current_url: str) -> Dict[str, Any]:
    """
    Extracts details directly from the listing card.
    """
    try:
        # Use specific classes from your HTML
        brand_loc = card.locator(".eui-card-header__title-container-title").first
        model_loc = card.locator(".eui-card-header__title-container-subtitle").first
        
        if await brand_loc.count() == 0:
            return None

        brand = (await brand_loc.inner_text()).strip()
        
        model_id = "N/A"
        if await model_loc.count() > 0:
            model_id = (await model_loc.inner_text()).strip()

        energy_class = "N/A"
        img_locator = card.locator("app-energy-thumbnail img").first
        if await img_locator.count() > 0:
            title_attr = await img_locator.get_attribute("title")
            if title_attr:
                energy_class = title_attr.replace("Energieklasse", "").replace("Energy class", "").strip()

        specs = {}
        param_rows = await card.locator("app-parameter-item-new").all()
        
        for row in param_rows:
            key_loc = row.locator("dt")
            val_loc = row.locator("dd")
            
            if await key_loc.count() > 0 and await val_loc.count() > 0:
                key_text = (await key_loc.inner_text()).strip()
                val_text = (await val_loc.inner_text()).strip()
                val_text = " ".join(val_text.split())
                if key_text:
                    specs[key_text] = val_text

        # FIXED: Removed dependency on actor_env.started_at which was crashing
        scraped_at = datetime.now(timezone.utc).isoformat()

        return {
            "brand": brand,
            "modelIdentifier": model_id,
            "energyClass": energy_class,
            "specifications": specs,
            "scrapedAt": scraped_at,
            "sourceUrl": current_url
        }

    except Exception as e:
        Actor.log.error(f"Error extracting card data: {str(e)}")
        return None

if __name__ == "__main__":
    asyncio.run(main())