-- ============================================
-- SCHEMA INITIALIZATION FOR ELT PIPELINE
-- ============================================

-- Create raw data table (IMMUTABLE)
CREATE TABLE IF NOT EXISTS raw_data_pollution (
    id BIGSERIAL PRIMARY KEY,
    measurement_date TIMESTAMP,
    station_code VARCHAR(50),
    station_name VARCHAR(255),
    so2 FLOAT,
    no2 FLOAT,
    o3 FLOAT,
    co FLOAT,
    pm10 FLOAT,
    pm25 FLOAT,
    so2_flag VARCHAR(10),
    no2_flag VARCHAR(10),
    o3_flag VARCHAR(10),
    co_flag VARCHAR(10),
    pm10_flag VARCHAR(10),
    pm25_flag VARCHAR(10),
    measurement_info TEXT,
    original_row_data JSONB,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_raw_entry UNIQUE (measurement_date, station_code, so2, no2, o3, co, pm10, pm25)
);

-- Create indexes on raw table for fast lookups
CREATE INDEX idx_raw_measurement_date ON raw_data_pollution(measurement_date);
CREATE INDEX idx_raw_station_code ON raw_data_pollution(station_code);
CREATE INDEX idx_raw_loaded_at ON raw_data_pollution(loaded_at);

-- Create analytics table (TRANSFORMATIONS RESULT)
CREATE TABLE IF NOT EXISTS analytics_pollution (
    id BIGSERIAL PRIMARY KEY,
    measurement_date DATE,
    station_code VARCHAR(50),
    station_name VARCHAR(255),
    so2_clean FLOAT,
    no2_clean FLOAT,
    o3_clean FLOAT,
    co_clean FLOAT,
    pm10_clean FLOAT,
    pm25_clean FLOAT,
    air_quality_index FLOAT,
    pollution_category VARCHAR(50),
    hourly_timestamp TIMESTAMP,
    data_quality_flag VARCHAR(20),
    transformed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes on analytics table
CREATE INDEX idx_analytics_date ON analytics_pollution(measurement_date);
CREATE INDEX idx_analytics_station ON analytics_pollution(station_code);
CREATE INDEX idx_analytics_aqi ON analytics_pollution(air_quality_index);

-- Create materialized view for daily aggregations
CREATE TABLE IF NOT EXISTS daily_aggregations_pollution (
    id BIGSERIAL PRIMARY KEY,
    aggregation_date DATE,
    station_code VARCHAR(50),
    station_name VARCHAR(255),
    avg_so2 FLOAT,
    avg_no2 FLOAT,
    avg_o3 FLOAT,
    avg_co FLOAT,
    avg_pm10 FLOAT,
    avg_pm25 FLOAT,
    max_aqi FLOAT,
    min_aqi FLOAT,
    avg_aqi FLOAT,
    records_count INTEGER,
    aggregated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes on daily aggregations
CREATE INDEX idx_daily_agg_date ON daily_aggregations_pollution(aggregation_date);
CREATE INDEX idx_daily_agg_station ON daily_aggregations_pollution(station_code);

-- Create audit table for tracking ELT runs
CREATE TABLE IF NOT EXISTS elt_audit_log (
    id BIGSERIAL PRIMARY KEY,
    dag_run_id VARCHAR(255),
    task_name VARCHAR(255),
    task_status VARCHAR(50),
    records_processed INTEGER,
    records_failed INTEGER,
    execution_time_seconds FLOAT,
    error_message TEXT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on audit log
CREATE INDEX idx_audit_created_at ON elt_audit_log(created_at);
CREATE INDEX idx_audit_dag_run ON elt_audit_log(dag_run_id);

-- Grant permissions to airflow user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO airflow;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO airflow;