import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.spiders import XMLFeedSpider, CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import mysql.connector
from datetime import datetime
import feedparser
import os

class NewsItem(scrapy.Item):
    title = scrapy.Field()
    content = scrapy.Field()
    url = scrapy.Field()
    source = scrapy.Field()
    published_date = scrapy.Field()
    location = scrapy.Field()

class RSSFeedSpider(XMLFeedSpider):
    name = 'rss_spider'
    iterator = 'iternodes'
    itertag = 'item'
    
    def __init__(self, *args, **kwargs):
        super(RSSFeedSpider, self).__init__(*args, **kwargs)
        self.feeds = [
            'http://rss.cnn.com/rss/cnn_latest.rss',
            'https://www.weather.gov/rss_page.php',
            'https://www.fema.gov/about/news-multimedia/rss',
        ]
    
    def parse_node(self, response, node):
        item = NewsItem()
        item['title'] = node.xpath('title/text()').get()
        item['content'] = node.xpath('description/text()').get()
        item['url'] = node.xpath('link/text()').get()
        item['source'] = response.url
        item['published_date'] = node.xpath('pubDate/text()').get()
        item['location'] = self.extract_location(item['content'])
        return item
    
    def extract_location(self, content):
        location_keywords = ['in', 'at', 'near']
        if content:
            words = content.split()
            for i, word in enumerate(words):
                if word.lower() in location_keywords and i + 1 < len(words):
                    return words[i + 1]
        return 'Unknown'

class NewsWebSpider(CrawlSpider):
    name = 'news_spider'
    allowed_domains = ['weather.gov', 'fema.gov', 'nhc.noaa.gov']
    start_urls = [
        'https://www.weather.gov/news/',
        'https://www.fema.gov/disasters',
        'https://www.nhc.noaa.gov/'
    ]
    
    rules = (
        Rule(
            LinkExtractor(
                allow=('disaster', 'emergency', 'storm', 'hurricane', 'flood')
            ),
            callback='parse_item'
        ),
    )
    
    def parse_item(self, response):
        item = NewsItem()
        item['title'] = response.css('h1::text').get()
        item['content'] = ' '.join(response.css('article p::text').getall())
        item['url'] = response.url
        item['source'] = response.url.split('/')[2]
        item['published_date'] = response.css('.date::text').get()
        item['location'] = self.extract_location(item['content'])
        return item
    
    def extract_location(self, content):
        return 'Unknown'

class NewsCollector:
    def __init__(self):
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': 'root',
            'database': 'disaster'
        }
        self.initialize_connection()
        self.setup_database()
        self.location_keywords = ['in', 'at', 'near', 'from', 'around', 'within']
        self.us_states = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
        self.disaster_types = ['earthquake', 'flood', 'hurricane', 'tornado', 'wildfire', 'storm', 'drought', 'landslide', 'tsunami']
    
    def initialize_connection(self):
        try:
            self.conn = mysql.connector.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            print("Database connection initialized successfully")
        except mysql.connector.Error as err:
            print(f"Error connecting to database: {err}")
            raise

    def setup_database(self):
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_data (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    content TEXT,
                    url VARCHAR(255) UNIQUE NOT NULL,
                    source VARCHAR(255) NOT NULL,
                    published_date VARCHAR(100),
                    location VARCHAR(100),
                    location_confidence FLOAT,
                    disaster_type VARCHAR(50),
                    cleaned_content TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            

            try:
                self.cursor.execute('CREATE INDEX idx_location ON news_data(location)')
                self.cursor.execute('CREATE INDEX idx_disaster_type ON news_data(disaster_type)')
                self.cursor.execute('CREATE INDEX idx_published_date ON news_data(published_date)')
                self.conn.commit()
            except mysql.connector.Error as err:
                if err.errno == 1061: 
                    print("Indexes already exist, continuing...")
                else:
                    raise
            print("Database tables created successfully")
        except mysql.connector.Error as err:
            print(f"Error setting up database: {err}")
            raise

    def store_item(self, item):
        try:

            content = item['content']
            source = item['source'].strip()
            

            if not content or not source:
                return
            
 
            location, confidence = self.extract_location(content)
            disaster_type = self.extract_disaster_type(item['title'] + ' ' + content)
            

            if not disaster_type:
                disaster_type = 'other'
            
            insert_query = """
                INSERT INTO news_data 
                (title, content, url, source, published_date, location, location_confidence, disaster_type, cleaned_content)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            self.cursor.execute(insert_query, (
                item['title'],
                content,
                item['url'],
                source,
                item['published_date'],
                location,
                confidence,
                disaster_type,
                self.clean_text(content)
            ))
            self.conn.commit()
            print(f"Successfully stored news item from {source}")
        except mysql.connector.IntegrityError:

            print(f"Duplicate entry found for URL: {item['url']}")
        except mysql.connector.Error as err:
            print(f"Database Error: {err}")
            self.conn.rollback()
    
    def collect_rss_feeds(self):
        """Collect news from RSS feeds using feedparser"""
        feeds = [
            'http://rss.cnn.com/rss/cnn_latest.rss',
            'https://www.weather.gov/rss_page.php',
            'https://www.fema.gov/about/news-multimedia/rss',
        ]
        
        print("Starting RSS feed collection...")
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                print(f"Processing {feed_url}...")
                for entry in feed.entries:
                    item = NewsItem()
                    item['title'] = entry.get('title', '')
                    item['content'] = entry.get('description', '')
                    item['url'] = entry.get('link', '')
                    item['source'] = feed_url
                    item['published_date'] = entry.get('published', '')
                    item['location'] = self.extract_location(item['content'])
                    self.store_item(item)
                print(f"Completed processing {feed_url}")
            except Exception as e:
                print(f"Error collecting RSS feed {feed_url}: {str(e)}")
        print("RSS feed collection completed!")

    def run(self):
        """Run the news collection process once"""
        try:
            print("Starting news collection process...")
            process = CrawlerProcess({
                'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'ROBOTSTXT_OBEY': True,
                'CONCURRENT_REQUESTS': 16,
                'DOWNLOAD_DELAY': 1,
            })
            

            process.crawl(RSSFeedSpider)
            process.crawl(NewsWebSpider)
            
 
            process.start()
            

            self.collect_rss_feeds()
            
            print("News collection process completed successfully!")
            
        except Exception as e:
            print(f"Error during news collection: {str(e)}")
        finally:
            self.conn.close()
    
    def clean_text(self, text):
        if not text:
            return ''

        text = ' '.join(text.split())

        text = ''.join(char for char in text if char.isalnum() or char in ' .,!?-')
        return text.strip()
    
    def extract_disaster_type(self, text):
        if not text:
            return None
        text = text.lower()
        for disaster in self.disaster_types:
            if disaster in text:
                return disaster
        return None

    def extract_location(self, content):
        if not content:
            return ('Unknown', 0.0)
        
        content = content.upper()
        words = content.split()
        

        for i, word in enumerate(words):
            if word in self.us_states:
                return (word, 0.9)
        

        for i, word in enumerate(words):
            if word.lower() in self.location_keywords and i + 1 < len(words):
                next_word = words[i + 1]

                if len(next_word) > 2 and not next_word.isdigit():
                    return (next_word, 0.7)
        
        return ('Unknown', 0.0)
    
    def run_scrapy_spiders(self):
        """Run Scrapy spiders to collect news data"""
        process = CrawlerProcess({
            'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'ROBOTSTXT_OBEY': True,
            'CONCURRENT_REQUESTS': 16,
            'DOWNLOAD_DELAY': 1,
            'COOKIES_ENABLED': False,
        })
        
        process.crawl(RSSFeedSpider)
        process.crawl(NewsWebSpider)
        process.start()
    
    def collect_all_news(self):
        """Collect news from all sources"""
        print("Collecting RSS feeds...")
        self.collect_rss_feeds()
        
        print("Running web scrapers...")
        self.run_scrapy_spiders()
        
        print("News collection completed!")
    
    def close(self):
        """Close database connection"""
        self.conn.close()

def main():
    collector = NewsCollector()
    try:
        collector.collect_all_news()
    finally:
        collector.close()

if __name__ == "__main__":
    main()

class NDMASpider(scrapy.Spider):
    name = 'ndma_spider'
    start_urls = ['https://ndma.gov.in/']
    
    def parse(self, response):
        # Extract news/disaster links from the main page
        news_links = response.css('a[href*="news"]::attr(href), a[href*="disaster"]::attr(href)').getall()
        for link in news_links:
            yield response.follow(link, self.parse_disaster)

    def parse_disaster(self, response):
        try:
            # Extract information from the disaster/news page
            title = response.css('h1::text, .entry-title::text').get('').strip()
            content = ' '.join(response.css('.entry-content p::text, article p::text').getall())
            
            # Extract date from content or metadata
            date_str = response.css('.entry-date::text, .post-date::text').get()
            date = self.parse_date(date_str) if date_str else datetime.now().strftime('%Y-%m-%d')
            
            item = {
                'type': self.extract_disaster_type(title + ' ' + content),
                'location': self.extract_location(content),
                'severity': self.determine_severity(content),
                'date': date,
                'description': content,
                'source': 'NDMA',
                'url': response.url,
                'latitude': self.extract_coordinates(content)[0],
                'longitude': self.extract_coordinates(content)[1]
            }
            
            Database.store_item(item)
            
        except Exception as e:
            print(f"Error parsing page {response.url}: {str(e)}")

    def parse_date(self, date_str):
        try:
            # Add various date format parsing patterns here
            date_patterns = [
                r'\d{2}-\d{2}-\d{4}',
                r'\d{4}-\d{2}-\d{2}',
                r'\d{2}/\d{2}/\d{4}'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, date_str)
                if match:
                    date_str = match.group(0)
                    return datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
            
            return datetime.now().strftime('%Y-%m-%d')
        except:
            return datetime.now().strftime('%Y-%m-%d')

    def extract_location(self, content):
        states = ['Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 
                 'Chhattisgarh', 'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh',
                 'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra',
                 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab',
                 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura',
                 'Uttar Pradesh', 'Uttarakhand', 'West Bengal']
        
        content = content.lower()
        for state in states:
            if state.lower() in content:
                return state
        return 'India'

    def extract_coordinates(self, content):
        # Try to find coordinates in the content
        coord_pattern = r'(\d+\.?\d*)\s*°?\s*[NS][,\s]+(\d+\.?\d*)\s*°?\s*[EW]'
        match = re.search(coord_pattern, content)
        
        if match:
            return float(match.group(1)), float(match.group(2))
        return None, None

    def extract_disaster_type(self, content):
        disaster_types = {
            'Flood': ['flood', 'flooding', 'inundation'],
            'Cyclone': ['cyclone', 'hurricane', 'storm'],
            'Earthquake': ['earthquake', 'seismic'],
            'Landslide': ['landslide', 'mudslide'],
            'Drought': ['drought', 'water scarcity'],
            'Heat Wave': ['heat wave', 'heatwave'],
            'Cold Wave': ['cold wave', 'coldwave'],
            'Urban Flood': ['urban flood'],
        }
        
        content = content.lower()
        for dtype, keywords in disaster_types.items():
            if any(keyword in content for keyword in keywords):
                return dtype
        return 'Other'

    def determine_severity(self, content):
        severity_indicators = {
            'High': ['severe', 'extreme', 'major', 'devastating'],
            'Medium': ['moderate', 'significant'],
            'Low': ['minor', 'slight', 'small']
        }
        
        content = content.lower()
        for severity, indicators in severity_indicators.items():
            if any(indicator in content for indicator in indicators):
                return severity
        return 'Medium'

class Database:
    @staticmethod
    def connect():
        return mysql.connector.connect(
            host='localhost',
            user='root',
            password='root',
            database='disaster'
        )

    @staticmethod
    def store_item(item):
        conn = Database.connect()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO disasters 
                (type, location, severity, date, description, source, latitude, longitude) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                item['type'],
                item['location'],
                item['severity'],
                item['date'],
                item['description'],
                item['source'],
                item['latitude'],
                item['longitude']
            ))
            conn.commit()
        except mysql.connector.Error as e:
            print(f"Database error: {str(e)}")
        finally:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    process = CrawlerProcess({
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'ROBOTSTXT_OBEY': True,
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 2,
    })
    process.crawl(NDMASpider)
    process.start()
