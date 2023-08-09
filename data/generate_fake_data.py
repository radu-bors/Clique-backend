# Import necessary libraries
import pandas as pd
import numpy as np
from faker import Faker
import random
import uuid
from datetime import datetime, timedelta

# Instantiate the Faker library
fake = Faker()

# Define the functions to generate the data
def generate_birthdate():
    """Generate a random birthdate between 18 and 50 years ago."""
    days_per_year = 365.24
    days_old_min = int(18 * days_per_year)
    days_old_max = int(50 * days_per_year)
    days_old = random.randint(days_old_min, days_old_max)
    birthdate = datetime.now() - timedelta(days=days_old)
    return birthdate.strftime("%d-%m-%Y")

def generate_location_in_berlin():
    """Generate a random location (latitude, longitude) in Berlin, Germany."""
    lat_min, lat_max = 52.379189, 52.677036
    lon_min, lon_max = 13.024405, 13.761117
    lat = random.uniform(lat_min, lat_max)
    lon = random.uniform(lon_min, lon_max)
    return f"({lat}, {lon})"

def generate_timestamp_past_week():
    """Generate a random timestamp from the past week."""
    seconds_per_week = 7 * 24 * 60 * 60
    seconds_ago = random.randint(0, seconds_per_week)
    timestamp = datetime.now() - timedelta(seconds=seconds_ago)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def generate_event(users_table, activities_table):
    """Generate a random event."""
    activity_id = random.choice(activities_table['activity_id'])
    initiated_by = random.choice(users_table['UID'])
    location = generate_location_in_berlin()
    min_age = random.randint(18, 35)
    max_age = random.randint(min_age, 50)
    pref_gender = generate_pref_gender_string()
    description = ' '.join(fake.sentences(random.randint(1, 3)))
    is_open = random.choice([True, False])
    initiated_on = generate_timestamp_past_week()
    return [str(uuid.uuid4()), activity_id, initiated_by, location, min_age, max_age, pref_gender, description, is_open, initiated_on]

def get_potential_participants(event, users_table):
    """Get the potential participants for an event."""
    potential_participants = users_table[(users_table['Birthdate'] >= event['min_age']) & (users_table['Birthdate'] <= event['max_age'])]
    potential_participants = potential_participants[potential_participants['Gender'].isin(event['pref_gender'])]
    return potential_participants

def generate_chat(num_messages, match):
    """Generate a random chat for a match."""
    chat = []
    for _ in range(num_messages):
        text = ' '.join(fake.sentences(random.randint(1, 3)))
        datetime = generate_timestamp_past_week()
        sender, recipient = random.choice([(match['creator'], match['participant']), (match['participant'], match['creator'])])
        chat.append([match['chat_id'], text, datetime, sender, recipient])
    return chat

def get_chat_block(match, chats_table):
    """Get the chat block for a match from the Chats table."""
    chat_block = chats_table[chats_table['chat_id'] == match['chat_id']]['text']
    return ' '.join(chat_block)

# Define a function to create the Users table.
def create_users_table(num_users):
    data = []
    for _ in range(num_users):
        user = generate_user()
        data.append(user)

    df = pd.DataFrame(data, columns=['Name', 'Birthdate', 'Gender', 'Location', 'UID', 'Last_online'])
    return df

# Define a function to create the Activities table.
def create_activities_table(num_activities):
    data = []
    for _ in range(num_activities):
        activity = generate_activity()
        data.append(activity)

    df = pd.DataFrame(data, columns=['activity_name', 'activity_id'])
    return df

# Define a function to create the Matches table.
def create_matches_table(max_participants_per_event, users_table, events_table):
    data = []
    for _, event in events_table.iterrows():
        # Get the potential participants for the event.
        potential_participants = get_potential_participants(event, users_table)
        # Get the number of participants for the event.
        num_participants = random.randint(1, min(max_participants_per_event, len(potential_participants)))
        # Get the participants for the event.
        participants = random.sample(list(potential_participants['UID']), num_participants)
        # Create a match for each participant.
        for participant in participants:
            match = [event['event_id'], event['initiated_by'], participant, False, uuid.uuid4(), ""]
            # Only one participant can be accepted for an event.
            if event['is_open'] and not any(row[3] for row in data if row[0] == event['event_id']):
                match[3] = True
                event['is_open'] = False
            data.append(match)

    df = pd.DataFrame(data, columns=['event_id', 'creator', 'participant', 'match', 'chat_id', 'chat_block'])
    return df

# Define a function to create the Chats table.
def create_chats_table(num_messages_per_chat, matches_table):
    data = []
    for _, match in matches_table.iterrows():
        chat = generate_chat(num_messages_per_chat, match)
        data.extend(chat)

    df = pd.DataFrame(data, columns=['chat_id', 'text', 'datetime', 'sender', 'recipient'])
    return df

# Generate Users table and Activities table
users_table = create_users_table(100)
activities_table = create_activities_table(6)

# Save the Users table and Activities table as CSV files
users_table.to_csv('/mnt/data/Users.csv', index=False)
activities_table.to_csv('/mnt/data/Activities.csv', index=False)

# Generate Events table
events_table = create_events_table(50, users_table, activities_table)
events_table.to_csv('/mnt/data/Events.csv', index=False)

# Create the Matches table and save it as a CSV file.
matches_table = create_matches_table(3, users_table, events_table)
matches_table.to_csv('/mnt/data/Matches.csv', index=False)

# Create the Chats table and save it as a CSV file.
chats_table = create_chats_table(5, matches_table)
chats_table.to_csv('/mnt/data/Chats.csv', index=False)

# Add the chat block to the Matches table.
matches_table['chat_block'] = matches_table.apply(lambda match: get_chat_block(match, chats_table), axis=1)

# Save the updated Matches table as a CSV file.
matches_table.to_csv('/mnt/data/Matches.csv', index=False)

events_table.head(), matches_table.head()
