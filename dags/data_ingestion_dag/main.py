import os
from datetime import timedelta
import sqlite3

import pandas as pd
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago


dag_path = os.getcwd()


def transform_data():
    print("Transform Data Start...")
    print(f"Dag path: {dag_path}")
    booking = pd.read_csv(f"{dag_path}/raw_data/booking.csv")
    client = pd.read_csv(f"{dag_path}/raw_data/client.csv")
    hotel = pd.read_csv(f"{dag_path}/raw_data/hotel.csv")

    # Join booking with client
    data = pd.merge(booking, client, on='client_id')
    data.rename(columns={'name': 'hotel_name', 'type': 'client_type'}, inplace=True)

    # Join booking, client and hotel
    data = pd.merge(data, hotel, on='hotel_id')
    data.rename(columns={'name': "hotel_name"}, inplace=True)

    # make date format consistent
    data.booking_date = pd.to_datetime(data.booking_date, format='mixed')

    # make all cost in GBP currency
    data.loc[data.currency == 'EUR', ['booking_cost']] = data.booking_cost * 0.8
    data.currency.replace("EUR", 'GBP', inplace=True)

    # remove unnecessary columns
    data = data.drop(columns=['address'])

    # load processed data
    data.to_csv(f"{dag_path}/processed_data/booking_records.csv", index=False)


def load_data():
    conn = sqlite3.connect('/opt/airflow/datascience.db')
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS booking_record (
            client_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL,
            room_type TEXT(512) NOT NULL,
            hotel_id INTEGER NOT NULL,
            booking_cost NUMERIC,
            currency TEXT,
            age INTEGER,
            client_name TEXT(512),
            client_type TEXT(512),
            hotel_name TEXT(512)
        );
    """)
    records = pd.read_csv(f"{dag_path}/processed_data/booking_records.csv")
    records.to_sql('booking_records', conn, if_exists='replace', index=False)


default_args = {
    'owner': 'airflow',
    'start_date': days_ago(5)
}

ingestion_dag = DAG(
    'booking_ingestion',
    default_args=default_args,
    description='Aggregates booking records for data analysis',
    schedule_interval=timedelta(days=1),
    catchup=False
)

task_1 = PythonOperator(
    task_id='transform_data',
    python_callable=transform_data,
    op_args=[" {{ ds }}"],
    dag=ingestion_dag
)

task_2 = PythonOperator(
    task_id='load_data',
    python_callable=load_data,
    dag=ingestion_dag
)

task_1 >> task_2
