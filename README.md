
-----

# Financial Data Pipeline & Dashboard

This project is a complete, end-to-end data pipeline that extracts data from three financial APIs (Alpha Vantage, NewsAPI, and FRED), stages it in a PostgreSQL database, transforms it into a clean star schema, and presents it in an interactive Flask web dashboard.

-----

## Key Features

  * **Data Extraction:** Ingests stock prices, financial news, and economic indicators from external APIs.
  * **Staging Database:** Persists raw API data in a PostgreSQL database before transformation.
  * **Data Transformation:** Uses SQL to clean, model, and load data into an analytics-ready star schema.
  * **Interactive Dashboard:** A Flask-based web application visualizes the data using Plotly charts.
  * **Automation:** The entire ELT (Extract, Load, Transform) pipeline is encapsulated in a single script, ready for scheduling.

-----

## 💻 Tech Stack

  * **Backend:** Python, Flask
  * **Database:** PostgreSQL
  * **Data Visualization:** Plotly
  * **APIs:** Alpha Vantage (Stocks), NewsAPI (News), FRED (Economic Data)

-----

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

  * Python 3.8+
  * PostgreSQL 12+
  * API Keys for:
      * [Alpha Vantage](https://www.google.com/search?q=https://www.alphavantage.co/support/%23api-key)
      * [NewsAPI](https://newsapi.org/register)
      * [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html)

-----

## 🔧 Installation & Setup

Follow these steps to get your local environment set up.

### 1\. Clone the Repository

```bash
git clone [https://github.com/CCallahan308/Financial_Dashboard_Project]
cd Dashboard_Project
```

### 2\. Set Up a Virtual Environment

It's highly recommended to use a virtual environment.

```bash
# Create the virtual environment
python -m venv venv

# Activate it (macOS/Linux)
source venv/bin/activate

# Activate it (Windows)
.\venv\Scripts\activate
```

### 3\. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4\. Set Up the PostgreSQL Database

You'll need to create a new database and a user for the pipeline.

```bash
# Create the database
createdb financial_dashboard

# Access psql to create a user and grant privileges
psql
```

Inside the `psql` shell, run the following commands:

```sql
-- Create a new user (role) with a secure password
CREATE USER dashboard_user WITH PASSWORD 'your_password';

-- Grant the user full privileges on the new database
GRANT ALL PRIVILEGES ON DATABASE financial_dashboard TO dashboard_user;

-- Exit psql
\q
```

### 5\. Run the Database Setup Script

This script will create the necessary staging and analytics tables.

```bash
# Run the setup_database.sql script
psql -d financial_dashboard -U dashboard_user -f setup_database.sql
```

### 6\. Configure Environment Variables

Copy the example `.env` file and add your credentials.

```bash
cp .env.example .env
```

Now, edit the `.env` file with your specific keys and database URL:

```ini
# .env
DATABASE_URL=postgresql://dashboard_user:your_password@localhost:5432/financial_dashboard
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
NEWSAPI_KEY=your_newsapi_key
FRED_API_KEY=your_fred_key
BASE_STOCK_SYMBOLS=AAPL,MSFT,GOOGL,TSLA
ECONOMIC_SERIES=GDP,UNRATE,CPIAUCSL,FEDFUNDS
```

-----

## 🚀 Usage

The project is split into two main parts: the pipeline and the web app.

### 1\. Run the Data Pipeline

To perform a one-time run of the ELT pipeline, execute:

```bash
python pipeline.py
```

This script will:

1.  Fetch stock prices (for symbols in `.env`) from Alpha Vantage.
2.  Fetch recent financial news from NewsAPI.
3.  Fetch economic indicators (for series in `.env`) from FRED.
4.  Load all raw data into the `staging` tables.
5.  Run the SQL transformations to populate the `analytics` star schema.

### 2\. Start the Web Dashboard

Once the pipeline has run at least once, you can start the Flask server:

```bash
python app.py
```

Open your browser and navigate to **`http://localhost:5000`** to see the dashboard.

-----

## 📊 Dashboard Features

  * **Summary Metrics:** At-a-glance view of monitored stocks, news articles, and economic indicators.
  * **Stock Price Trends:** Interactive line charts showing 30-day price history.
  * **Trading Volume:** Bar charts displaying daily trading volume for each security.
  * **Financial News:** A filterable feed of the latest news articles.
  * **Economic Indicators:** Key macroeconomic trends visualized over time.
  * **Dynamic UI:** Charts are interactive (zoom, pan) and the dashboard data refreshes automatically.

-----

## 📁 Project Structure

```
Dashboard_Project/
├── app.py              # The Flask web dashboard
├── pipeline.py         # The main ELT pipeline script
├── setup_database.sql  # SQL schema for all tables
├── transform.sql       # SQL queries for the transformation (T) step
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── .gitignore
└── README.md
```

-----

## ⚙️ Configuration

You can customize the stocks and economic indicators fetched by the pipeline by editing your `.env` file.

### Change Stock Symbols

Add or remove symbols (comma-separated) to the `BASE_STOCK_SYMBOLS` variable.

```ini
BASE_STOCK_SYMBOLS=AAPL,MSFT,GOOGL,TSLA,AMZN,NVDA
```

### Change Economic Indicators

Add or remove FRED series IDs (comma-separated) to the `ECONOMIC_SERIES` variable.

```ini
ECONOMIC_SERIES=GDP,UNRATE,CPIAUCSL,FEDFUNDS,DGS10
```

-----

## ⏰ Scheduling the Pipeline (Automation)

You can automate the pipeline to run on a schedule.

### Linux/macOS (Cron)

1.  Open your crontab editor:
    ```bash
    crontab -e
    ```
2.  Add a line to run the pipeline. This example runs it every hour:
    ```cron
    # Runs at the top of every hour
    0 * * * * /path/to/Dashboard_Project/venv/bin/python /path/to/Dashboard_Project/pipeline.py
    ```
    **Note:** Make sure to use the absolute paths to your virtual environment's Python and your `pipeline.py` script.

### Windows (Task Scheduler)

1.  Open **Task Scheduler**.
2.  Create a "Basic Task".
3.  Set the "Trigger" to "Daily" or "Hourly."
4.  Set the "Action" to "Start a program."
5.  In "Program/script," browse to your virtual environment's `python.exe` (e.g., `C:\path\to\Dashboard_Project\venv\Scripts\python.exe`).
6.  In "Add arguments (optional)," add `pipeline.py`.
7.  In "Start in (optional)," add the path to your project directory (e.g., `C:\path\to\Dashboard_Project\`).

-----

## SCHEMA Database Schema

The database is split into two schemas: `staging` for raw data and `analytics` for the final star schema.

### Staging Schema (Raw Data)

  * `staging.raw_stock_prices`: Raw JSON or text data from Alpha Vantage.
  * `staging.raw_news_articles`: Raw JSON or text data from NewsAPI.
  * `staging.raw_econ_data`: Raw JSON or text data from FRED.

### Analytics Schema (Star Schema)

  * **Dimension Tables:**
      * `analytics.dim_date`
      * `analytics.dim_security`
      * `analytics.dim_economic_indicator`
  * **Fact Tables:**
      * `analytics.fact_prices`
      * `analytics.fact_news`
      * `analytics.fact_economics`

-----

## 🔍 Troubleshooting

  * **Database Connection Errors:**

      * Ensure the PostgreSQL service is running.
      * Verify your `DATABASE_URL` in `.env` is correct (username, password, port).
      * Confirm the `dashboard_user` has `ALL PRIVILEGES` on the `financial_dashboard` database.

  * **API Key Errors:**

      * Check that your keys are correct in the `.env` file.
      * Check the API dashboards (Alpha Vantage, NewsAPI) to ensure you have not hit your free-tier rate limits.

  * **Dashboard is Empty:**

      * Run `python pipeline.py` manually and check for errors in the console or `pipeline.log`.
      * Use `psql` or a database GUI to check if the `analytics` tables have data.

### Data Integrity Checks

Run these queries in `psql` to verify data is being loaded.

```sql
-- Check if staging tables are populated
SELECT COUNT(*) FROM staging.raw_stock_prices;
SELECT COUNT(*) FROM staging.raw_news_articles;
SELECT COUNT(*) FROM staging.raw_econ_data;

-- Check if analytics tables are populated after transform
SELECT COUNT(*) FROM analytics.fact_prices;
SELECT COUNT(*) FROM analytics.fact_news;
SELECT COUNT(*) FROM analytics.fact_economics;
```

-----

## 📈 Future Improvements

  * **Database Indexing:** Add indexes to fact table foreign keys and date dimensions to speed up dashboard queries.
  * **Connection Pooling:** Implement connection pooling for the Flask app to handle concurrent users more efficiently.
  * **Incremental Loads:** Modify the pipeline to only fetch new data instead of full-loading, reducing redundancy.
  * **Data Quality Checks:** Add explicit data quality checks (e.g., for nulls, duplicates) to the transformation step.

-----

## 🤝 Contributing

Contributions are welcome\! Please feel free to:

1.  Fork the repository.
2.  Create a new feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes.
4.  Push to the branch and open a Pull Request.

-----

## 📝 License

This project is licensed under the MIT License.
