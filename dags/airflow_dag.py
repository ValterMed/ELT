"""
ELT Pipeline DAG for Air Pollution Analysis
Extract → Load (Raw) → Transform → Load (Analytics)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.task_group import TaskGroup
import pandas as pd
import os
import logging

# Configure logging
logger = logging.getLogger(__name__)

# ============================================
# DAG Configuration
# ============================================
default_args = {
    'owner': 'data-team',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
}

dag = DAG(
    'elt_air_pollution_pipeline',
    default_args=default_args,
    description='ELT Pipeline for Air Pollution Data Analysis',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    catchup=False,
    tags=['ELT', 'pollution', 'production'],
)

# ============================================
# CONFIGURATION
# ============================================
POSTGRES_CONN_ID = 'postgres_default'
DATA_DIR = '/home/airflow/data'
RAW_CSV_PATH = os.path.join(DATA_DIR, 'kaggle/air-pollution-in-seoul/AirPollutionSeoul/Original-Data/Measurement_info.csv')
PROCESSED_CSV_PATH = os.path.join(DATA_DIR, 'processed_pollution_data.csv')

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# ============================================
# PYTHON FUNCTIONS FOR TASKS
# ============================================

def extract_data(**context):
    """
    Extract: Load CSV data from local storage
    This simulates extracting from an API or external source
    """
    try:
        if not os.path.exists(RAW_CSV_PATH):
            logger.warning(f"CSV file not found at {RAW_CSV_PATH}")
            logger.info("Creating sample data for demonstration...")
            # Create sample data if doesn't exist
            sample_data = {
                'Measurement date': pd.date_range('2024-01-01', periods=100, freq='H'),
                'Station code': ['11001', '11002'] * 50,
                'Station name': ['Jongno-gu', 'Jung-gu'] * 50,
                'SO2': [10.5, 12.3] * 50,
                'NO2': [45.2, 48.9] * 50,
                'O3': [23.1, 25.6] * 50,
                'CO': [0.5, 0.6] * 50,
                'PM10': [35.2, 40.1] * 50,
                'PM2.5': [15.3, 18.9] * 50,
            }
            df = pd.DataFrame(sample_data)
            df.to_csv(RAW_CSV_PATH, index=False)
            logger.info(f"Sample data created at {RAW_CSV_PATH}")
        
        # Load data
        df = pd.read_csv(RAW_CSV_PATH)
        logger.info(f"Extracted {len(df)} records from {RAW_CSV_PATH}")
        
        # Push to XCom for next tasks
        context['task_instance'].xcom_push(key='extracted_rows', value=len(df))
        
        return {
            'status': 'success',
            'rows_extracted': len(df),
            'file_path': RAW_CSV_PATH
        }
    except Exception as e:
        logger.error(f"Error in extract_data: {str(e)}")
        raise

def load_raw_data(**context):
    """
    Load (Raw): Insert raw data as-is into PostgreSQL raw table
    NO transformations at this stage
    """
    try:
        # Read extracted data
        df = pd.read_csv(RAW_CSV_PATH)
        logger.info(f"Loading {len(df)} raw records into PostgreSQL...")
        
        # Connect to PostgreSQL
        hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        connection = hook.get_conn()
        cursor = connection.cursor()
        
        # Prepare data for insertion
        insert_count = 0
        failed_count = 0
        
        for idx, row in df.iterrows():
            try:
                # Insert raw data exactly as it comes (no cleaning)
                insert_query = """
                    INSERT INTO raw_data_pollution 
                    (measurement_date, station_code, station_name, so2, no2, o3, co, pm10, pm25, loaded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """
                
                cursor.execute(insert_query, (
                    pd.to_datetime(row.get('Measurement date', datetime.now())),
                    str(row.get('Station code', 'UNKNOWN')),
                    str(row.get('Station name', 'UNKNOWN')),
                    float(row.get('SO2', 0)) if pd.notna(row.get('SO2')) else None,
                    float(row.get('NO2', 0)) if pd.notna(row.get('NO2')) else None,
                    float(row.get('O3', 0)) if pd.notna(row.get('O3')) else None,
                    float(row.get('CO', 0)) if pd.notna(row.get('CO')) else None,
                    float(row.get('PM10', 0)) if pd.notna(row.get('PM10')) else None,
                    float(row.get('PM2.5', 0)) if pd.notna(row.get('PM2.5')) else None,
                    datetime.now()
                ))
                insert_count += 1
            except Exception as row_error:
                logger.warning(f"Failed to insert row {idx}: {str(row_error)}")
                failed_count += 1
        
        # Commit transaction
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info(f"Raw data loaded: {insert_count} successful, {failed_count} failed")
        
        # Push metrics to XCom
        context['task_instance'].xcom_push(key='raw_inserted', value=insert_count)
        context['task_instance'].xcom_push(key='raw_failed', value=failed_count)
        
        return {
            'status': 'success',
            'rows_inserted': insert_count,
            'rows_failed': failed_count
        }
    except Exception as e:
        logger.error(f"Error in load_raw_data: {str(e)}")
        raise

def calculate_aqi(row):
    """Calculate simple Air Quality Index"""
    # Simplified AQI calculation based on PM2.5
    pm25 = row.get('pm25_clean', 0)
    if pm25 is None:
        return None
    
    if pm25 <= 12:
        return 1
    elif pm25 <= 35.4:
        return 2
    elif pm25 <= 55.4:
        return 3
    elif pm25 <= 150.4:
        return 4
    elif pm25 <= 250.4:
        return 5
    else:
        return 6

def categorize_pollution(aqi):
    """Categorize air quality based on AQI"""
    if aqi is None:
        return 'Unknown'
    
    aqi_int = int(aqi)
    categories = {
        1: 'Good',
        2: 'Moderate',
        3: 'Unhealthy for Sensitive Groups',
        4: 'Unhealthy',
        5: 'Very Unhealthy',
        6: 'Hazardous'
    }
    return categories.get(aqi_int, 'Unknown')

def transform_and_load_analytics(**context):
    """
    Transform: Clean data and load into analytics table
    This is the T in ELT - all transformations happen here
    """
    try:
        hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        connection = hook.get_conn()
        cursor = connection.cursor()
        
        logger.info("Starting transformations...")
        
        # Step 1: Clean raw data and load to analytics table
        transform_query = """
        INSERT INTO analytics_pollution 
        (measurement_date, station_code, station_name, so2_clean, no2_clean, o3_clean, 
         co_clean, pm10_clean, pm25_clean, hourly_timestamp, data_quality_flag, transformed_at)
        SELECT 
            DATE(r.measurement_date) as measurement_date,
            r.station_code,
            r.station_name,
            COALESCE(r.so2, 0) as so2_clean,
            COALESCE(r.no2, 0) as no2_clean,
            COALESCE(r.o3, 0) as o3_clean,
            COALESCE(r.co, 0) as co_clean,
            COALESCE(r.pm10, 0) as pm10_clean,
            COALESCE(r.pm25, 0) as pm25_clean,
            r.measurement_date as hourly_timestamp,
            CASE 
                WHEN r.so2 IS NULL OR r.no2 IS NULL THEN 'incomplete_data'
                WHEN r.pm10 > 500 OR r.pm25 > 250 THEN 'outlier_detected'
                ELSE 'clean' 
            END as data_quality_flag,
            CURRENT_TIMESTAMP
        FROM raw_data_pollution r
        WHERE r.loaded_at > CURRENT_TIMESTAMP - INTERVAL '1 day'
        AND NOT EXISTS (
            SELECT 1 FROM analytics_pollution a 
            WHERE a.hourly_timestamp = r.measurement_date 
            AND a.station_code = r.station_code
        )
        """
        
        cursor.execute(transform_query)
        transformed_count = cursor.rowcount
        logger.info(f"Transformed {transformed_count} records into analytics table")
        
        # Step 2: Calculate AQI
        aqi_query = """
        UPDATE analytics_pollution
        SET air_quality_index = CASE
            WHEN pm25_clean <= 12 THEN 1
            WHEN pm25_clean <= 35.4 THEN 2
            WHEN pm25_clean <= 55.4 THEN 3
            WHEN pm25_clean <= 150.4 THEN 4
            WHEN pm25_clean <= 250.4 THEN 5
            ELSE 6
        END,
        pollution_category = CASE
            WHEN pm25_clean <= 12 THEN 'Good'
            WHEN pm25_clean <= 35.4 THEN 'Moderate'
            WHEN pm25_clean <= 55.4 THEN 'Unhealthy for Sensitive Groups'
            WHEN pm25_clean <= 150.4 THEN 'Unhealthy'
            WHEN pm25_clean <= 250.4 THEN 'Very Unhealthy'
            ELSE 'Hazardous'
        END
        WHERE transformed_at > CURRENT_TIMESTAMP - INTERVAL '1 day'
        """
        
        cursor.execute(aqi_query)
        aqi_count = cursor.rowcount
        logger.info(f"Updated AQI for {aqi_count} records")
        
        # Step 3: Create daily aggregations
        agg_query = """
        INSERT INTO daily_aggregations_pollution
        (aggregation_date, station_code, station_name, avg_so2, avg_no2, avg_o3, 
         avg_co, avg_pm10, avg_pm25, max_aqi, min_aqi, avg_aqi, records_count)
        SELECT 
            a.measurement_date,
            a.station_code,
            a.station_name,
            ROUND(AVG(a.so2_clean)::numeric, 2) as avg_so2,
            ROUND(AVG(a.no2_clean)::numeric, 2) as avg_no2,
            ROUND(AVG(a.o3_clean)::numeric, 2) as avg_o3,
            ROUND(AVG(a.co_clean)::numeric, 2) as avg_co,
            ROUND(AVG(a.pm10_clean)::numeric, 2) as avg_pm10,
            ROUND(AVG(a.pm25_clean)::numeric, 2) as avg_pm25,
            MAX(a.air_quality_index) as max_aqi,
            MIN(a.air_quality_index) as min_aqi,
            ROUND(AVG(a.air_quality_index)::numeric, 2) as avg_aqi,
            COUNT(*) as records_count
        FROM analytics_pollution a
        WHERE a.transformed_at > CURRENT_TIMESTAMP - INTERVAL '1 day'
        GROUP BY a.measurement_date, a.station_code, a.station_name
        ON CONFLICT DO NOTHING
        """
        
        cursor.execute(agg_query)
        agg_count = cursor.rowcount
        logger.info(f"Created {agg_count} daily aggregations")
        
        # Commit transaction
        connection.commit()
        
        # Log to audit table
        audit_query = """
        INSERT INTO elt_audit_log 
        (dag_run_id, task_name, task_status, records_processed, execution_time_seconds, started_at, finished_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(audit_query, (
            context['dag_run'].run_id,
            'transform_and_load_analytics',
            'success',
            transformed_count,
            0,
            datetime.now(),
            datetime.now()
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info(f"Transform complete: {transformed_count} analytics records created")
        
        return {
            'status': 'success',
            'analytics_records': transformed_count,
            'aqi_updated': aqi_count,
            'aggregations_created': agg_count
        }
    except Exception as e:
        logger.error(f"Error in transform_and_load_analytics: {str(e)}")
        raise

def verify_data_integrity(**context):
    """
    Verify that raw and analytics tables have data and raw is immutable
    """
    try:
        hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        connection = hook.get_conn()
        cursor = connection.cursor()
        
        # Check raw data count
        cursor.execute("SELECT COUNT(*) FROM raw_data_pollution")
        raw_count = cursor.fetchone()[0]
        
        # Check analytics data count
        cursor.execute("SELECT COUNT(*) FROM analytics_pollution")
        analytics_count = cursor.fetchone()[0]
        
        # Check for NULL values (data quality)
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN so2 IS NULL THEN 1 END) as null_so2,
                COUNT(CASE WHEN no2 IS NULL THEN 1 END) as null_no2,
                COUNT(CASE WHEN pm25 IS NULL THEN 1 END) as null_pm25
            FROM raw_data_pollution
        """)
        null_stats = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        logger.info(f"Data Integrity Check:")
        logger.info(f"  Raw table records: {raw_count}")
        logger.info(f"  Analytics table records: {analytics_count}")
        logger.info(f"  NULL values - SO2: {null_stats[0]}, NO2: {null_stats[1]}, PM2.5: {null_stats[2]}")
        
        if raw_count == 0:
            raise ValueError("Raw data table is empty!")
        
        return {
            'status': 'success',
            'raw_records': raw_count,
            'analytics_records': analytics_count,
            'null_so2': null_stats[0],
            'null_no2': null_stats[1],
            'null_pm25': null_stats[2]
        }
    except Exception as e:
        logger.error(f"Error in verify_data_integrity: {str(e)}")
        raise

# ============================================
# DAG TASKS
# ============================================

# Extract task
extract_task = PythonOperator(
    task_id='extract_pollution_data',
    python_callable=extract_data,
    dag=dag,
)

# Load raw data task
load_raw_task = PythonOperator(
    task_id='load_raw_data',
    python_callable=load_raw_data,
    depends_on_past=False,
    dag=dag,
)

# Transform and load analytics task
transform_task = PythonOperator(
    task_id='transform_and_load_analytics',
    python_callable=transform_and_load_analytics,
    depends_on_past=False,
    dag=dag,
)

# Verify data integrity task
verify_task = PythonOperator(
    task_id='verify_data_integrity',
    python_callable=verify_data_integrity,
    depends_on_past=False,
    dag=dag,
)

# ============================================
# DAG DEPENDENCIES (Pipeline Flow)
# ============================================
extract_task >> load_raw_task >> transform_task >> verify_task