# Dynamics of User Behavior on Twitter

A comprehensive research project analyzing behavioral patterns and topic dynamics of Twitter users through data collection, topic modeling, and clustering analysis.

## Project Overview

This project investigates how Twitter users' behavioral patterns change over time by examining their tweet content, profile modifications, and social network dynamics. Using advanced machine learning techniques including topic modeling and clustering, we identify distinct user behavior patterns and analyze the evolution of user interests and engagement.

## Features

- **Automated Data Collection**: Web scraping tools for collecting tweets and user profile information
- **Topic Classification**: BERTopic-based classification system organizing tweets into 11 major topic categories
- **Behavioral Analysis**: Comprehensive analysis of user activity patterns, topic diversity, and profile changes
- **Clustering Analysis**: K-means clustering to identify 12 distinct user behavior groups
- **Temporal Dynamics**: Tracking of user behavior changes over time periods

## Dataset Structure

### Core Data Files

- `analysis/master.csv` - Main dataset with user features and behavioral metrics
- `analysis/posts_classified.csv.zip` - Classified tweets with topic assignments
- `analysis/user_topics.csv` - User-level topic analysis and activity metrics
- `data/PostsTable.xlsx` - Raw tweet collection data
- `data/UsersTable.xlsx` - User profile information

### Analysis Results

- `analysis/FinalChangesSummary.csv` - Summary of all user profile changes
- `analysis/Followers_Changes.csv` - Follower count dynamics
- `analysis/Following_Changes.csv` - Following count dynamics  
- `analysis/Bio_Changes.csv` - Biography update patterns
- `analysis/master_with_clusters_k12.csv` - Clustered user groups

## Methodology

### 1. Data Collection
- **Tweet Scraping**: Automated collection using Selenium WebDriver
- **Profile Monitoring**: Tracking changes in user profiles over time
- **Language Filtering**: English-only tweets for consistency

### 2. Topic Modeling
- **Text Preprocessing**: Cleaning, emoji removal, stopword filtering
- **BERTopic Implementation**: Multilingual BERT embeddings for topic extraction
- **Topic Categories**: 11 major topics including Politics, Crypto, Economy, Health, etc.

### 3. Feature Engineering
- `num_topics`: Number of unique topics per user
- `tweets_per_day`: Daily posting frequency
- `dominant_topic_id`: Most frequent topic category
- `delta_followers_changes`: Net follower count changes
- `delta_following_changes`: Net following count changes
- `delta_bio_changes`: Biography modification frequency

### 4. Clustering Analysis
- **K-Means Clustering**: Optimal k=12 clusters identified via silhouette analysis
- **PCA Visualization**: 2D projection for cluster interpretation
- **User Segmentation**: Distinct behavioral profiles from casual to super-active users

## Key Findings

### Topic Distribution
- **Economy**: 13,825 tweets (dominant category)
- **Conflict**: 16,623 tweets (current events focus)
- **Crypto**: 13,754 tweets (financial technology)
- **Politics**: 11,896 tweets (political discourse)
- **Other categories**: Lifestyle, Health, Climate, Tech, Sports, Education, Religion

### User Behavior Clusters
- **Cluster Analysis**: 12 distinct user groups ranging from casual users to super-active influencers
- **Activity Patterns**: Most users (90%) fall into 3-4 "normal" clusters; remaining 10% show extreme behaviors
- **Profile Dynamics**: Users with high follower changes and frequent bio updates may indicate account rebranding or inauthentic behavior

## Technical Stack

- **Python**: Core programming language
- **Selenium**: Web scraping automation
- **BERTopic**: Topic modeling framework  
- **scikit-learn**: Machine learning and clustering
- **pandas**: Data manipulation and analysis
- **plotly/matplotlib**: Data visualization
- **NLTK**: Natural language processing

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/Dynamics-users-of-behavior-on-twitter.git
cd Dynamics-users-of-behavior-on-twitter

# Install required packages
pip install -r requirements.txt

# Install additional dependencies for topic modeling
pip install bertopic sentence-transformers umap-learn hdbscan
```

## Usage

### Data Collection
```bash
python code/twitter_scraper.py      # Collect tweets by hashtag
python code/profile_scraper.py      # Monitor user profile changes
```

### Analysis
Open and run the Jupyter notebook:
```bash
jupyter notebook dynamics_behavior_of_users_on_twitter.ipynb
```

## File Structure

```
├── analysis/                    # Processed datasets and results
│   ├── master.csv              # Main feature dataset
│   ├── posts_classified.csv.zip # Topic-classified tweets
│   └── *_Changes.csv           # Profile change tracking
├── code/                       # Data collection scripts
│   ├── twitter_scraper.py      # Tweet collection
│   └── profile_scraper.py      # Profile monitoring
├── data/                       # Raw collected data
│   ├── PostsTable.xlsx         # Raw tweets
│   └── UsersTable.xlsx         # User profiles
└── dynamics_behavior_of_users_on_twitter.ipynb  # Main analysis
```

## Research Applications

- **Social Media Analytics**: Understanding user engagement patterns
- **Content Strategy**: Identifying trending topics and user preferences
- **Behavioral Research**: Studying online social dynamics
- **Bot Detection**: Identifying unusual behavioral patterns
- **Marketing Research**: Audience segmentation and targeting

## Contributors

This project was developed as part of academic research into social media user behavior dynamics.

## License

This project is for research and educational purposes. Please ensure compliance with Twitter's Terms of Service when collecting data.

## Citation

If you use this work in your research, please cite accordingly and respect data privacy guidelines.
