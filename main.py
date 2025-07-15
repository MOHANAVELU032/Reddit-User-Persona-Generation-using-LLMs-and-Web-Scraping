import os
import time
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("webdriver_manager not found. Installing now...")
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "webdriver-manager"])
    from webdriver_manager.chrome import ChromeDriverManager

# --- Gemini 2.0 Flash API Setup ---
from google import genai

GOOGLE_API_KEY = "AIzaSyDiyavWE6m213K3vheJcYLqzy_3RwBx8H0"  # Replace with your actual API key
client = genai.Client(api_key=GOOGLE_API_KEY)
MODEL_ID = "gemini-2.0-flash"  # or "gemini-2.0-flash-001" if required

def configure_selenium():
    """Configure Selenium WebDriver with Chrome options"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error setting up ChromeDriver: {e}")
        print("Make sure you have Chrome installed on your system.")
        return None

def scrape_reddit_profile(driver, profile_url):
    """Scrape posts and comments from Reddit profile by clicking tabs"""
    print(f"Scraping profile: {profile_url}")
    try:
        driver.get(profile_url)
        time.sleep(3)

        # Click the 'Posts' tab (second <a> in tabgroup)
        try:
            posts_tab = driver.find_element(By.XPATH, '//*[@id="profile-feed-tabgroup"]/a[2]')
            posts_tab.click()
            time.sleep(2)
        except Exception as e:
            print("Could not click Posts tab (may already be selected):", e)

        # Scroll to load more posts
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        posts = []
        for a in soup.find_all('a', attrs={'slot': 'full-post-link'}):
            try:
                post_url = a.get('href', '')
                title_tag = a.find('faceplate-screen-reader-content')
                title = title_tag.text.strip() if title_tag else ''
                posts.append({
                    'type': 'post',
                    'title': title,
                    'url': f"https://www.reddit.com{post_url}" if post_url.startswith('/') else post_url
                })
            except Exception as e:
                print(f"Error parsing post: {e}")
                continue

        # Click the 'Comments' tab (third <a> in tabgroup)
        try:
            comments_tab = driver.find_element(By.XPATH, '//*[@id="profile-feed-tabgroup"]/a[3]')
            comments_tab.click()
            time.sleep(2)
        except Exception as e:
            print("Could not click Comments tab:", e)

        # Scroll to load more comments
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        comments = []
        for a in soup.find_all('a', attrs={'data-ks-id': True}):
            if a['data-ks-id'].startswith('t1_'):
                try:
                    comment_url = a.get('href', '')
                    comments.append({
                        'type': 'comment',
                        'url': f"https://www.reddit.com{comment_url}" if comment_url.startswith('/') else comment_url
                    })
                except Exception as e:
                    print(f"Error parsing comment: {e}")
                    continue

        # Extract basic profile info (username from URL)
        profile_info = {}
        try:
            username = ""
            if "/user/" in profile_url:
                username = profile_url.rstrip('/').split("/user/")[-1].split('/')[0]
            profile_info['username'] = username
        except Exception as e:
            print(f"Error parsing profile info: {e}")

        return {
            'profile_info': profile_info,
            'posts': posts,
            'comments': comments
        }
    except Exception as e:
        print(f"Error scraping profile: {e}")
        return None

def generate_persona_from_file(profile_txt_file):
    """Generate user persona using Gemini 2.0 Flash from structured text file"""
    try:
        with open(profile_txt_file, 'r', encoding='utf-8') as f:
            profile_txt = f.read()
        prompt = f"""
        Analyze the following Reddit user's profile data and create a detailed user persona.\n\
        Include sections for: Demographics, Interests, Behavior Patterns, Personality Traits,\n\
        and any other relevant categories. For each characteristic in the persona, include\n\
        citations from the user's posts or comments that support your analysis.\n\
        For each citation, refer to the post or comment by its section and index (e.g., POST [2](link of post), COMMENT [5](link of comment)).\n\
        \n\
        Profile Data:\n\
        {profile_txt}\n\
        Structure your response like this:\n\
        === USER PERSONA ===\n\
        [Username]: [value] (source: [citation])\n\
        === DEMOGRAPHICS ===\n\
        - [Characteristic]: [value] (source: [citation])\n\
        === INTERESTS ===\n\
        - [Interest]: [evidence] (source: [citation])\n\
        === BEHAVIOR PATTERNS ===\n\
        - [Behavior]: [evidence] (source: [citation])\n\
        === PERSONALITY TRAITS ===\n\
        - [Trait]: [evidence] (source: [citation])\n\
        === OTHER OBSERVATIONS ===\n\
        - [Observation]: [evidence] (source: [citation])\n\
        """
        response = client.models.generate_content(model=MODEL_ID, contents=[prompt])
        return response.text
    except Exception as e:
        print(f"Error generating persona: {e}")
        return None

def save_persona_to_file(username, persona_text):
    """Save the generated persona to a text file"""
    try:
        if not username:
            username = "reddit_user"
        filename = f"{username}_persona.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(persona_text)
        print(f"Persona saved to {filename}")
        return filename
    except Exception as e:
        print(f"Error saving persona file: {e}")
        return None

def save_profile_data_to_file(profile_data, filename):
    """Save posts and comments to a structured text file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=== PROFILE INFO ===\n")
            for k, v in profile_data.get('profile_info', {}).items():
                f.write(f"{k.capitalize()}: {v}\n")
            f.write("\n=== POSTS ===\n")
            for idx, post in enumerate(profile_data.get('posts', []), 1):
                f.write(f"[{idx}]\n")
                f.write(f"Title: {post.get('title', '')}\n")
                f.write(f"Content: {post.get('content', '')}\n")
                f.write(f"Subreddit: {post.get('subreddit', '')}\n")
                f.write(f"Timestamp: {post.get('timestamp', '')}\n\n")
            f.write("=== COMMENTS ===\n")
            for idx, comment in enumerate(profile_data.get('comments', []), 1):
                f.write(f"[{idx}]\n")
                f.write(f"Content: {comment.get('content', '')}\n")
                f.write(f"Subreddit: {comment.get('subreddit', '')}\n")
                f.write(f"Timestamp: {comment.get('timestamp', '')}\n\n")
        print(f"Profile data saved to {filename}")
        return filename
    except Exception as e:
        print(f"Error saving profile data: {e}")
        return None

def main():
    profile_url = input("Enter Reddit profile URL: ").strip()
    
    # Initialize Selenium
    driver = configure_selenium()
    if not driver:
        print("Failed to initialize browser. Exiting.")
        return
    
    try:
        # Scrape profile data
        profile_data = scrape_reddit_profile(driver, profile_url)
        if not profile_data:
            print("Failed to scrape profile data. Exiting.")
            return
        
        # Save profile data to file
        username = profile_data['profile_info'].get('username', 'reddit_user')
        data_filename = f"{username}_data.txt"
        save_profile_data_to_file(profile_data, data_filename)
        
        # Generate persona
        print("Generating persona...")
        persona_text = generate_persona_from_file(data_filename)
        if not persona_text:
            print("Failed to generate persona. Exiting.")
            return
        
        # Save to file
        save_persona_to_file(username, persona_text)
        
        # Print persona to console
        print("\nGenerated Persona:")
        print(persona_text)
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()