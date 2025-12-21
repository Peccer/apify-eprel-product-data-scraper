FROM apify/actor-python-playwright:3.11

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy the rest of the code
COPY . ./

# Run the actor
CMD ["python3", "-m", "main"]
