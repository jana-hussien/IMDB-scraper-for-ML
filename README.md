# IMDb Genre Data Scraper and Trailer Downloader

A python script to scrape IMDb movie data by genre, process the information, and downloadd the audio as well as sample images from the trailer video to use to train machine learning models.


## Requirements
- Python 3.x
- Selenium WebDriver (e.g., ChromeDriver)
- Libraries: `pandas`, `selenium`, `requests`, `yt_dlp`, `opencv-python`, `video_sampler`
- TMDb API Token (required for fetching trailer URLs)

- Install the required Python libraries:  
  ```
  pip install -U video_sampler pandas selenium requests yt-dlp opencv-python
  ```
- Ensure you have a valid TMDb API token and set it in the script.

## Output
- A CSV file (`IMDb_Genres_Data.csv`) containing movie metadata.
- Trailer audio and sampled frames downloaded into a specified directory.

The CSV file includes columns such as:
- Title
- Genre(s)
- Runtime (in minutes)
- IMDb Score
- Votes
- IMDb ID

