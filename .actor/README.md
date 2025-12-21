# EPREL Product Data Scraper

Extract high-value product energy efficiency data directly from the **European Product Registry for Energy Labelling (EPREL)**.

## Features
- **Comprehensive Extraction**: Scrapes model identifiers, supplier names, energy classes, and full technical specifications.
- **Document Links**: Automatically discovers links to the official Product Information Sheets (PIS) and Energy Label PDFs.
- **Support for All Categories**: Works across all EPREL product groups (Appliances, Lighting, Displays, etc.).
- **Dynamic Content Support**: Built with Playwright to handle the dynamic Angular frontend of the registry.

## Sample Output
```json
{
  "url": "https://eprel.ec.europa.eu/screen/product/refrigeratingappliances2019/390977",
  "modelIdentifier": "KGN36VIEB",
  "supplierName": "Bosch",
  "energyClass": "E",
  "productInformationSheet": "https://eprel.ec.europa.eu/screen/product/refrigeratingappliances2019/390977/pis",
  "energyLabelPdf": "https://eprel.ec.europa.eu/screen/product/refrigeratingappliances2019/390977/label",
  "specifications": {
    "Annual energy consumption (kWh/a)": "238",
    "Total volume (dm3 or l)": "326",
    "Airborne acoustical noise emissions (dB(A) re 1 pW)": "39"
  }
}
```

## Cost Estimation
Using the Pay-per-result model, this scraper is highly cost-effective for compliance monitoring or market research. 
- Estimated price: **$0.02 - $0.05 per 100 items** depending on proxy usage and complexity.

## Usage
Simply provide the URL of a product category (e.g., `https://eprel.ec.europa.eu/screen/product/washingmachines2019`) or a list of specific product IDs.
