import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import re
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def stable_fallback_date(identifier):
    """Generate a stable date from a URL or title hash."""
    hash_val = abs(hash(identifier)) % 730
    epoch = datetime(2023, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)
    return epoch + timedelta(days=hash_val)


def fetch_engineering_page():
    """Fetch the OpenAI engineering page using cloudscraper to bypass Cloudflare."""
    try:
        logger.info("Fetching OpenAI engineering page with cloudscraper...")
        scraper = cloudscraper.create_scraper()
        response = scraper.get("https://openai.com/news/engineering/")
        response.raise_for_status()
        logger.info("Successfully fetched engineering page")
        return response.text
    except Exception as e:
        logger.error(f"Error fetching engineering page: {e}")
        raise


def parse_engineering_html(html_content):
    """Parse the HTML content from OpenAI's Engineering News page."""
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []

    for a in soup.find_all("a", href=True):
        try:
            href = a.get("href", "")
            text = a.get_text(strip=True)

            # Only process /index/ links (articles)
            if "/index/" not in href:
                continue

            # Skip if text is too short (not an article)
            if len(text) < 20:
                continue

            # Parse title and date from combined text
            # Format is usually: "Title HereEngineeringMon DD, YYYY"
            date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),\s+(\d{4})', text)

            if date_match:
                date_str = date_match.group(0)
                # Extract title by removing the date and "Engineering" tag
                title = re.sub(r'Engineering(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec).*$', '', text).strip()
                try:
                    date = datetime.strptime(date_str, "%b %d, %Y")
                    date = date.replace(tzinfo=pytz.UTC)
                except Exception:
                    date = stable_fallback_date(href)
            else:
                title = text.replace("Engineering", "").strip()
                date = stable_fallback_date(href)

            # Build full URL
            link = f"https://openai.com{href}" if href.startswith("/") else href

            # Skip duplicates
            if any(article["link"] == link for article in articles):
                continue

            articles.append({
                "title": title,
                "link": link,
                "date": date,
                "category": "Engineering",
                "description": title,
            })
            logger.info(f"Found article: {title} ({date.strftime('%Y-%m-%d')})")

        except Exception as e:
            logger.warning(f"Skipping an article due to parsing error: {e}")
            continue

    logger.info(f"Parsed {len(articles)} articles")
    return articles


def generate_rss_feed(articles, feed_name="openai_engineering"):
    """Generate RSS feed from parsed articles."""
    fg = FeedGenerator()
    fg.title("OpenAI Engineering News")
    fg.description("Latest engineering news and updates from OpenAI")
    fg.link(href="https://openai.com/news/engineering")
    fg.language("en")

    # Sort by date, newest first
    articles_sorted = sorted(articles, key=lambda x: x["date"], reverse=True)

    for article in articles_sorted:
        fe = fg.add_entry()
        fe.title(article["title"])
        fe.link(href=article["link"])
        fe.description(article["description"])
        fe.published(article["date"])
        fe.category(term=article["category"])
        fe.id(article["link"])

    logger.info("RSS feed generated successfully")
    return fg


def save_rss_feed(feed_generator, feed_name="openai_engineering"):
    """Save RSS feed to an XML file."""
    feeds_dir = Path(__file__).parent.parent / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    output_file = feeds_dir / f"feed_{feed_name}.xml"
    feed_generator.rss_file(str(output_file), pretty=True)
    logger.info(f"RSS feed saved to {output_file}")
    return output_file


def main():
    """Main function to generate OpenAI Engineering News RSS feed."""
    try:
        html_content = fetch_engineering_page()
        articles = parse_engineering_html(html_content)
        if not articles:
            logger.warning("No articles were parsed. Check your selectors.")
            return False
        feed = generate_rss_feed(articles)
        save_rss_feed(feed)
        return True
    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {e}")
        return False


if __name__ == "__main__":
    main()
