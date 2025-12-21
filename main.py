import asyncio
from typing import Dict, Any, List
from urllib.parse import urljoin
from datetime import datetime, timezone

from playwright.async_api import async_playwright
from apify import Actor

async def main():
    async with Actor:
        # 1. Initialize input
        actor_input = await Actor.get_input() or {}
        start_urls = actor_input.get("startUrls", [{"url": "https://eprel.ec.europa.eu/screen/product/refrigeratingappliances2019"}])
        max_results = actor_input.get("maxResults", 100)

        Actor.log.info(f"Starting EPREL Scraper for {len(start_urls)} URLs.")

        # Get the environment to check for headless mode
        actor_env = Actor.get_env()

        async with async_playwright() as p:
            # 2. Setup browser and proxy
            # REPLACED: Actor.config.headless -> actor_env.get('headless')
            browser = await p.chromium.launch(
                headless=actor_env.get('headless', True),
                proxy={"server": None}
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
                Actor.log.info(f"Processing source URL: {url}")

                try:
                    # Navigate to the page
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # Handle EPREL's dynamic loading
                    if "/screen/product/" not in url:
                        Actor.log.info("Interpreting URL as a search/listing page...")
                        await page.wait_for_selector(".product-item-title", timeout=15000)
                        
                        product_links = await page.eval_on_selector_all(
                            ".product-item-title a", 
                            "(links) => links.map(a => a.href)"
                        )
                        Actor.log.info(f"Found {len(product_links)} products on list page.")
                        
                        for p_link in product_links:
                            if scraped_count >= max_results:
                                break
                            
                            # Navigate to individual product
                            product_data = await scrape_product_page(page, p_link)
                            if product_data:
                                await Actor.push_data(product_data)
                                scraped_count += 1
                                Actor.log.info(f"Scraped {scraped_count}/{max_results}: {p_link}")
                    
                    else:
                        # Direct product page
                        product_data = await scrape_product_page(page, url)
                        if product_data:
                            await Actor.push_data(product_data)
                            scraped_count += 1
                            Actor.log.info(f"Scraped direct product {scraped_count}: {url}")

                except Exception as e:
                    Actor.log.error(f"Failed to process {url}: {str(e)}")

            await browser.close()
            Actor.log.info(f"Scraping finished. Total items: {scraped_count}")

async def scrape_product_page(page, url) -> Dict[str, Any]:
    """Helper to extract details from a specific EPREL product page."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # EPREL uses Angular; wait for a specific element that appears late
        await page.wait_for_selector(".product-model-identifier", timeout=20000)
        
        # Extract base info
        model_id = await page.inner_text(".product-model-identifier") if await page.query_selector(".product-model-identifier") else "N/A"
        supplier = await page.inner_text(".product-supplier-name") if await page.query_selector(".product-supplier-name") else "N/A"
        
        # Extract Energy Class
        energy_class = await page.get_attribute(".energy-label-box .energy-class", "class")
        # Clean the energy class string (e.g., "energy-class A")
        energy_class = energy_class.split()[-1] if energy_class else "N/A"

        # Extract technical parameters from the table
        params = {}
        rows = await page.query_selector_all("tr")
        for row in rows:
            cells = await row.query_selector_all("td")
            if len(cells) >= 2:
                key = (await cells[0].inner_text()).strip()
                val = (await cells[1].inner_text()).strip()
                if key:
                    params[key] = val

        # Extract Document Links
        pis_link = await page.get_attribute("a[href*='productInformationSheet']", "href")
        label_link = await page.get_attribute("a[href*='energyLabel']", "href")
        
        # REPLACED: Actor.config.start_at -> actor_env.started_at
        actor_env = Actor.get_env()
        scraped_at = actor_env.started_at.isoformat() if actor_env.started_at else datetime.now(timezone.utc).isoformat()

        return {
            "url": url,
            "modelIdentifier": model_id.strip(),
            "supplierName": supplier.strip(),
            "energyClass": energy_class,
            "productInformationSheet": urljoin(url, pis_link) if pis_link else None,
            "energyLabelPdf": urljoin(url, label_link) if label_link else None,
            "specifications": params,
            "scrapedAt": scraped_at
        }
    except Exception as e:
        Actor.log.warning(f"Could not scrape product {url}: {str(e)}")
        return None

if __name__ == "__main__":
    asyncio.run(main())
