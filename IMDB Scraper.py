from dotenv import load_dotenv
import time
import ast
import re
import os
import requests
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import yt_dlp

######################################################
#   Variables to specify:
######################################################


# TMDb API Authorization Token
TMDB_API_TOKEN = "REDACTED"

# number of times to click "Show 50 more"
range_movies = 20

# genres = {
#     0: "action", 1: "adventure", 2: "animation", 3: "biography", 4: "comedy",
#     5: "crime", 6: "documentary", 7: "drama", 8: "family", 9: "fantasy",
#     10: "film-noir", 11: "game-show", 12: "history", 13: "horror", 14: "music",
#     15: "musical", 16: "mystery", 17: "news", 18: "reality-tv", 19: "romance",
#     20: "sci-fi", 21: "sport", 22: "talk-show", 23: "thriller", 24: "war",
#     25: "western"
# }
genres = {
    5: "crime"
}

# Path to existing CSV file
existing_csv_path = "IMDb_Genres_Data.csv"

######################################################
# END
######################################################


# Load existing DataFrame or create a new one if file doesn't exist
if os.path.exists(existing_csv_path):
    existing_df = pd.read_csv(existing_csv_path)
else:
    existing_df = pd.DataFrame(columns=["Genre", "Title", "Runtime (min)", "IMDb Score", "Votes", "IMDb ID", "Poster URL"])

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
        return str(imdb_id)
    except Exception as e:
        print(f"Error extracting IMDb ID: {e}")
        return None

def get_movie_poster(element):
    """Extract and download movie poster."""
    try:
        img_element = element.find_element(By.XPATH, './/div[contains(@class, "ipc-media")]/img')
        poster_url = img_element.get_attribute('src')
        return poster_url
    except Exception as e:
        print(f"Error extracting poster URL: {e}")
        return None

def download_audio(trailer_url, output_dir, imdb_id):
    """Download trailer audio with yt-dlp using minimal storage/time"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        options = {
            'format': 'worstaudio[ext=webm]/worstaudio/worst', 
            'outtmpl': os.path.join(output_dir, f"{imdb_id}"),
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',  # More efficient than MP3
                'preferredquality': '0',   # Lowest quality setting
            }],
            'postprocessor_args': ['-metadata', 'comment='],  # Strip metadata
            'writemetadata': False,        # Disable metadata file
            'audio-quality': '32K',        # Explicit low bitrate
            'writethumbnail': False,       # No cover art
            'noprogress': True,            # Reduces output processing
            'external_downloader': 'aria2c',  # Faster downloads
            'external_downloader_args': ['-x16', '-s16', '-j16']
        }
        
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([trailer_url])
            
    except Exception as e:
        print(f"Error downloading audio for {imdb_id}: {e}")


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



    
load_dotenv()

    
    # Initialize the WebDriver
driver = webdriver.Chrome()


all_data_dict = {}  # Dictionary to store unique movies by IMDb ID
existing_dict = existing_df.to_dict(orient="index")
formatted_dict = {}
for idx, row in existing_dict.items():
    imdb_id = row["IMDb ID"]  # Use IMDb ID as the key
    formatted_dict[imdb_id] = {
        "Genre": ast.literal_eval(row["Genre"]) if isinstance(row["Genre"], str) else row["Genre"],
        "Title": row["Title"],
        "Runtime (min)": row["Runtime (min)"],
        "IMDb Score": row["IMDb Score"],
        "Votes": row["Votes"],
        "IMDb ID": imdb_id,
        "Poster URL": row["Poster URL"],
    }
existing_dict = formatted_dict
exist_count = 0
for index, genre in genres.items():
    url = f"https://www.imdb.com/search/title/?title_type=feature&genres={genre}&release_date=2000-01-01,2025-12-31"
    driver.get(url)

    # Maximize window and wait for page load
    driver.maximize_window()
    time.sleep(3)
    for i in range(range_movies):
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

    elements = driver.find_elements(By.XPATH, '//*[@id="__next"]/main/div[2]/div[3]/section/section/div/section/section/div[2]/div/section/div[2]/div[2]/ul/li')

    for index, element in enumerate(elements, start=1):
        text = element.text.strip()
        lines = text.split("\n") 

        title = lines[0].split('. ', 1)[-1] if lines and '. ' in lines[0] else lines[0] if lines else None
        runtime = lines[2] if len(lines) > 2 else None
        imdb_score = lines[4] if len(lines) > 4 else None
        votes = lines[5] if len(lines) > 5 else None

        imdb_id = get_imdb_id(element)
        poster_url = get_movie_poster(element)

        if imdb_id in existing_dict:
            exist_count+= 1
            # Update genres for existing movie
            existing_genres = existing_dict[imdb_id]["Genre"]
            cur_genre = [key for key, value in genres.items() if value == genre]
            for g in cur_genre:
                if g not in existing_dict[imdb_id]["Genre"]:
                    existing_dict[imdb_id]["Genre"].append(g)
                
        else:
            # Add new movie entry
            all_data_dict[imdb_id] = {
                "Genre": [key for key, value in genres.items() if value == genre],
                "Title": title,
                "Runtime (min)": parse_runtime(runtime) if runtime else None,
                "IMDb Score": parse_imdb_score(imdb_score),
                "Votes": parse_votes(votes),
                "IMDb ID": imdb_id,
                "Poster URL": poster_url,
            }
print("EXIST COUNT", exist_count)
existing_df = pd.DataFrame.from_dict(existing_dict, orient="index")

# Convert dictionary to DataFrame
new_data_df = pd.DataFrame(all_data_dict.values())

# Create main data directory
folder_name = "data_" + "_".join(list(genres.values()))
data_dir = os.path.join(os.path.dirname(__file__), folder_name)
os.makedirs(data_dir, exist_ok=True)

# Define subdirectories
audio_dir = os.path.join(data_dir, "audios")
poster_dir = os.path.join(data_dir, "posters")
os.makedirs(audio_dir, exist_ok=True)
os.makedirs(poster_dir, exist_ok=True)

# List to store valid rows
valid_rows = []

# Process each row to validate and download resources
for idx, row in new_data_df.iterrows():
    imdb_id = row["IMDb ID"]
    
    # Check if files already exist for this movie
    audio_file = os.path.join(audio_dir, f"{imdb_id}.opus")
    poster_file = os.path.join(poster_dir, f"{imdb_id}.jpg")
    files_exist = os.path.exists(audio_file) and os.path.exists(poster_file)
    
    # If files already exist, consider it valid and continue
    if files_exist:
        print(f"Files already exist for {imdb_id}, adding to valid rows")
        valid_rows.append(row)
        continue
    
    # Skip if no poster URL
    if pd.isna(row["Poster URL"]):
        print(f"Skipping {imdb_id}: No poster URL available")
        continue
    
    # Check for trailer availability first without downloading
    trailer_url = get_trailer_url(imdb_id)
    if not trailer_url:
        print(f"Skipping {imdb_id}: No trailer available")
        continue
    
    # Validate poster URL is accessible
    poster_url = row["Poster URL"]
    try:
        response = requests.head(poster_url)
        response.raise_for_status()
    except Exception as e:
        print(f"Skipping {imdb_id}: Poster URL not accessible - {e}")
        continue
    
    # Download resources
    download_success = True
    try:
        # Download trailer audio
        download_audio(trailer_url, audio_dir, imdb_id)
        
        # Verify audio file was created
        if not os.path.exists(audio_file):
            print(f"Audio download failed for {imdb_id} - file not found")
            download_success = False
    except Exception as e:
        print(f"Error downloading audio for {imdb_id}: {e}")
        download_success = False
    
    if not download_success:
        # Clean up any existing files
        if os.path.exists(audio_file):
            os.remove(audio_file)
        continue
    
    # Now download poster
    try:
        response = requests.get(poster_url)
        response.raise_for_status()
        with open(poster_file, 'wb') as f:
            f.write(response.content)
        print(f"Poster saved: {imdb_id}.jpg")
    except Exception as e:
        print(f"Poster download failed for {imdb_id}: {e}")
        # Clean up audio file since poster failed
        if os.path.exists(audio_file):
            os.remove(audio_file)
        continue
    
    # All resources downloaded successfully, add to valid rows
    valid_rows.append(row)

valid_df = pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame(columns=new_data_df.columns)

valid_df.dropna(axis = 0, how = 'all', inplace = True)
valid_df.dropna(subset=["Poster URL"], inplace=True)
existing_df.dropna(axis = 0, how = 'all', inplace = True)
existing_df.dropna(subset=["Poster URL"], inplace=True)


df = pd.concat([existing_df, valid_df])
                       
# Drop movies without a poster or trailer audio
df.reset_index(drop=True, inplace=True)

# Save the valid DataFrame
csv_path = os.path.join(data_dir, "IMDb_Genres_Data.csv")
if not df.empty:
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"Data saved successfully to {csv_path}! Total df rows: {len(df)}, Total new rows: {len(valid_df)}")
else:
    print("No valid rows found. CSV not created.")


driver.quit()
