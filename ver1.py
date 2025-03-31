import time
import re
import os
import requests
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import yt_dlp
import cv2
import subprocess
from io import BytesIO


# TMDb API Authorization Token
TMDB_API_TOKEN = "REDACTED"

def parse_runtime(runtime_str):
    """Convert '1h 40m' format to total minutes"""
    hours = re.findall(r'(\d+)h', runtime_str)
    minutes = re.findall(r'(\d+)m', runtime_str)
    total_minutes = 0
    if hours:
        total_minutes += int(hours[0]) * 60
    if minutes:
        total_minutes += int(minutes[0])
    return int(total_minutes) if total_minutes > 0 else None

def parse_votes(votes_str):
    """Convert vote strings like '1.9M', '24K' to numeric values"""
    if not votes_str or not isinstance(votes_str, str):
        return None
    
    votes_str = re.sub(r'[(),\s]', '', votes_str)
    
    try:
        if votes_str.endswith('K'):
            return int(float(votes_str[:-1]) * 1000)
        elif votes_str.endswith('M'):
            return int(float(votes_str[:-1]) * 1000000)
        else:
            return int(votes_str)
    except ValueError:
        return None

def parse_imdb_score(score_str):
    """Ensure IMDb score is numeric or set it to None"""
    try:
        return float(score_str) if score_str and score_str.replace('.', '', 1).isdigit() else None
    except ValueError:
        return None

def get_imdb_id(element):
    """Extract IMDb ID from the movie element."""
    try:
        link = element.find_element(By.TAG_NAME, 'a').get_attribute('href')
        imdb_id = re.search(r'/title/(tt\d+)/', link).group(1) if link else None
        return imdb_id
    except Exception as e:
        print(f"Error extracting IMDb ID: {e}")
        return None

def process_video_stream(url, output_dir, hash_size=3, buffer_size=20):
    """
    Sample frames from a YouTube video using the video_sampler tool with yt-dlp integration.
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Construct the video_sampler command
        command = [
            "video_sampler", "hash", url, output_dir,
            "--hash-size", str(hash_size),
            "--buffer-size", str(buffer_size),
            '''--ytdlp --yt-extra-args '--match-filter "original_url!*=/shorts/ & url!*=/shorts/"'''
        ]
        
        # Execute the command
        subprocess.run(command, check=True)
        
        print(f"Frames successfully sampled from {url} and saved to {output_dir}")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while sampling frames: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

def get_trailer_url(imdb_id):
    """Fetch the trailer URL using TMDb API."""
    try:
        url = f"https://api.themoviedb.org/3/movie/{imdb_id}/videos?language=en-US"
        headers = {
            "accept": "application/json",
            "Authorization": TMDB_API_TOKEN,
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        # Filter for trailers only
        for video in data.get("results", []):
            if video["type"] == "Trailer" and video["site"] == "YouTube":
                trailer_url = f"https://www.youtube.com/watch?v={video['key']}"
                print(trailer_url)
                return trailer_url
        
        print(f"No trailer found for IMDb ID: {imdb_id}")
        return None
    except Exception as e:
        print(f"Error fetching trailer for IMDb ID {imdb_id}: {e}")
        return None


# Initialize the WebDriver
driver = webdriver.Chrome()

# genres = {
#     1: "action", 2: "adventure", 3: "animation", 4: "biography", 5: "comedy",
#     6: "crime", 7: "documentary", 8: "drama", 9: "family", 10: "fantasy",
#     11: "film-noir", 12: "game-show", 13: "history", 14: "horror", 15: "music",
#     16: "musical", 17: "mystery", 18: "news", 19: "reality-tv", 20: "romance",
#     21: "sci-fi", 22: "sport", 23: "talk-show", 24: "thriller", 25: "war",
#     26: "western"
# }
genres = {
    1: "action", 2: "adventure"
}

all_data = []

for index, genre in genres.items():
    url = f"https://www.imdb.com/search/title/?title_type=feature&genres={genre}"
    driver.get(url)

    # Maximize window and wait for page load
    driver.maximize_window()
    time.sleep(5)

    # Step to click the "show more" button multiple times (if available)
    for i in range(1):
        try:
            buttons = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, "//span[contains(text(), ' more')]"))
            )

            for button in buttons:
                text = button.text
                if re.search(r'\d+', text):
                    driver.execute_script("arguments[0].click();", button)
                    break

            time.sleep(1)
        except Exception:
            break

    # XPath to find all list items (li elements)
    elements = driver.find_elements(By.XPATH, '//*[@id="__next"]/main/div[2]/div[3]/section/section/div/section/section/div[2]/div/section/div[2]/div[2]/ul/li')

    # Extracting and formatting data for the current genre
    genre_data = []
    for index, element in enumerate(elements, start=1):
        text = element.text.strip()
        lines = text.split("\n") 

        title = lines[0].split('. ', 1)[-1] if lines and '. ' in lines[0] else lines[0] if lines else None
        runtime = lines[2] if len(lines) > 2 else None
        imdb_score = lines[4] if len(lines) > 4 else None
        votes = lines[5] if len(lines) > 5 else None

        imdb_id = get_imdb_id(element)

        existing_movie = next((movie for movie in genre_data if movie["IMDb ID"] == imdb_id), None)

        if existing_movie:
            # Add the current genre to the list of genres if not already present
            current_genre = [key for key, value in genres.items() if value == genre]
            for g in current_genre:
                if g not in existing_movie["Genre"]:
                    existing_movie["Genre"].append(g)
        else:
            # Add new movie entry to genre_data
            genre_data.append({
                "Genre": [key for key, value in genres.items() if value == genre],
                "Title": title,
                "Runtime (min)": parse_runtime(runtime) if runtime else None,
                "IMDb Score": parse_imdb_score(imdb_score),
                "Votes": parse_votes(votes),
                "IMDb ID": imdb_id,
            })

    all_data.extend(genre_data)

# Convert to DataFrame
df = pd.DataFrame(all_data)

# Remove columns where all values are NaN
df.dropna(axis=1, how='all', inplace=True)

# Define the directory where you want to save the file and trailers
save_directory = r"YOUR TARGET DIRECTORY"
trailer_directory = os.path.join(save_directory, "Trailers")
os.makedirs(trailer_directory, exist_ok=True)

# Save DataFrame to CSV
file_path = os.path.join(save_directory, "IMDb_Genres_Data.csv")
df.to_csv(file_path, index=False, encoding="utf-8")

print(f"Data saved successfully to {file_path}!")

# Download trailers for each movie using IMDb IDs
for idx, row in df.iterrows():
    imdb_id = row["IMDb ID"]
    
    if imdb_id:
        trailer_url = get_trailer_url(imdb_id)
        
        if trailer_url:
            process_video_stream(trailer_url, save_directory)

# Close the browser
driver.quit()
