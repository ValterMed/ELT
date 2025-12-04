#!/usr/bin/env python3
"""
Script to download Air Pollution dataset from Kaggle
Run this BEFORE starting Airflow to have the data ready

Requirements:
1. Install kaggle: pip install kaggle
2. Set up Kaggle API credentials:
   - Go to https://www.kaggle.com/settings/account
   - Click "Create New API Token"
   - This downloads kaggle.json
   - Place it at ~/.kaggle/kaggle.json
   - chmod 600 ~/.kaggle/kaggle.json

Run: python download_dataset.py
"""

import os
import sys
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_kaggle_setup():
    """Verify Kaggle API is properly configured"""
    kaggle_config = os.path.expanduser('~/.kaggle/kaggle.json')
    if not os.path.exists(kaggle_config):
        logger.error("❌ Kaggle API not configured!")
        logger.info("Setup instructions:")
        logger.info("1. Install kaggle: pip install kaggle")
        logger.info("2. Go to https://www.kaggle.com/settings/account")
        logger.info("3. Click 'Create New API Token' to download kaggle.json")
        logger.info("4. Place kaggle.json at ~/.kaggle/kaggle.json")
        logger.info("5. Run: chmod 600 ~/.kaggle/kaggle.json")
        return False
    
    logger.info("✓ Kaggle API configured")
    return True

def download_dataset():
    """Download the Air Pollution dataset from Kaggle"""
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        
        # Initialize Kaggle API
        api = KaggleApi()
        api.authenticate()
        
        logger.info("Authenticated with Kaggle API")
        
        # Dataset info
        dataset = 'bappekim/air-pollution-in-seoul'
        output_path = './data/kaggle'
        
        # Create output directory
        os.makedirs(output_path, exist_ok=True)
        logger.info(f"Downloading dataset: {dataset}")
        
        # Download dataset
        api.dataset_download_files(dataset, path=output_path, unzip=True)
        
        logger.info(f"✓ Dataset downloaded to {output_path}")
        
        # List downloaded files
        if os.path.exists(output_path):
            files = os.listdir(output_path)
            logger.info(f"Files downloaded: {files}")
            return True
        else:
            logger.error("Download directory not found")
            return False
            
    except ImportError:
        logger.error("❌ kaggle package not installed")
        logger.info("Install with: pip install kaggle")
        return False
    except Exception as e:
        logger.error(f"❌ Error downloading dataset: {str(e)}")
        return False

def prepare_data_for_airflow():
    """
    Combine and prepare data for Airflow ingestion
    Converts Kaggle CSVs to a single file that Airflow will load
    """
    try:
        data_path = './data/kaggle'
        output_path = './data/raw_pollution_data.csv'
        
        if not os.path.exists(data_path):
            logger.warning(f"Dataset path not found: {data_path}")
            logger.info("Creating sample data for demonstration...")
            create_sample_data(output_path)
            return True
        
        logger.info("Preparing data for Airflow...")
        
        # Look for Measurement_info.csv (the main dataset)
        files = os.listdir(data_path)
        csv_files = [f for f in files if f.endswith('.csv')]
        
        if not csv_files:
            logger.error("No CSV files found in dataset")
            create_sample_data(output_path)
            return False
        
        logger.info(f"Found CSV files: {csv_files}")
        
        # Load and combine data
        dfs = []
        for csv_file in csv_files:
            file_path = os.path.join(data_path, csv_file)
            logger.info(f"Reading {csv_file}...")
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
                logger.info(f"  Rows: {len(df)}, Columns: {len(df.columns)}")
                dfs.append(df)
            except Exception as e:
                logger.warning(f"  Failed to read {csv_file}: {str(e)}")
        
        if dfs:
            # Combine all dataframes
            combined_df = pd.concat(dfs, ignore_index=True)
            logger.info(f"Combined dataset: {len(combined_df)} rows, {len(combined_df.columns)} columns")
            
            # Save for Airflow
            os.makedirs('./data', exist_ok=True)
            combined_df.to_csv(output_path, index=False)
            logger.info(f"✓ Data prepared and saved to {output_path}")
            
            # Show sample
            logger.info("\nSample data (first 3 rows):")
            logger.info(combined_df.head(3).to_string())
            
            return True
        else:
            logger.error("No data could be loaded from CSV files")
            create_sample_data(output_path)
            return False
            
    except Exception as e:
        logger.error(f"Error preparing data: {str(e)}")
        create_sample_data(output_path)
        return False

def create_sample_data(output_path):
    """Create sample/synthetic data for demonstration"""
    logger.info("Creating sample synthetic data...")
    
    import pandas as pd
    from datetime import datetime, timedelta
    import numpy as np
    
    # Create synthetic data
    dates = pd.date_range('2024-01-01', periods=500, freq='H')
    
    data = {
        'Measurement date': dates,
        'Station code': np.random.choice(['11001', '11002', '11003', '11004'], size=len(dates)),
        'Station name': np.random.choice(['Jongno-gu', 'Jung-gu', 'Songpa-gu', 'Gangbuk-gu'], size=len(dates)),
        'SO2': np.random.uniform(5, 50, size=len(dates)),
        'NO2': np.random.uniform(20, 100, size=len(dates)),
        'O3': np.random.uniform(10, 80, size=len(dates)),
        'CO': np.random.uniform(0.2, 2.0, size=len(dates)),
        'PM10': np.random.uniform(15, 150, size=len(dates)),
        'PM2.5': np.random.uniform(5, 100, size=len(dates)),
    }
    
    df = pd.DataFrame(data)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    
    logger.info(f"✓ Sample data created at {output_path}")
    logger.info(f"  Shape: {df.shape}")
    logger.info("\nSample rows:")
    logger.info(df.head().to_string())

def main():
    """Main execution"""
    logger.info("=" * 60)
    logger.info("AIR POLLUTION DATASET DOWNLOADER")
    logger.info("=" * 60)
    
    # Check Kaggle setup
    if check_kaggle_setup():
        # Download from Kaggle
        if download_dataset():
            # Prepare data for Airflow
            if prepare_data_for_airflow():
                logger.info("\n✓ SUCCESS: Data ready for Airflow!")
                logger.info("Next steps:")
                logger.info("1. Place this data in ./data/raw_pollution_data.csv")
                logger.info("2. Start Airflow with: docker-compose up -d")
                logger.info("3. Access Airflow at http://localhost:8080")
                return 0
    
    # Fallback: create sample data
    logger.info("\nCreating sample data as fallback...")
    create_sample_data('./data/raw_pollution_data.csv')
    logger.info("✓ Sample data ready!")
    logger.info("You can use this to test the pipeline")
    return 0

if __name__ == '__main__':
    sys.exit(main())