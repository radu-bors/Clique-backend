-- create the Users table
CREATE TABLE Users (
    Name TEXT NOT NULL,
    Birthdate DATE NOT NULL,
    Gender TEXT NOT NULL CHECK (Gender IN ('male', 'female', 'other')),
    Location POINT NOT NULL,
    UID UUID NOT NULL PRIMARY KEY,
    Last_online TIMESTAMP NOT NULL
);
-- Copy the Users table
\copy Users FROM '/home/rbors/Documents/app_project/data/Users.csv' DELIMITER ',' CSV HEADER NULL 'NULL';

-- create the Activities table
CREATE TABLE Activities (
    activity_name TEXT NOT NULL,
    activity_id UUID NOT NULL PRIMARY KEY
);
-- Copy the Activities table
\copy Activities FROM '/home/rbors/Documents/app_project/data/Activities.csv' DELIMITER ',' CSV HEADER NULL 'NULL';

-- create Events table
CREATE TABLE Events (
    event_id UUID NOT NULL PRIMARY KEY,
    activity_id UUID NOT NULL REFERENCES Activities(activity_id),
    initiated_by UUID NOT NULL REFERENCES Users(UID),
    location POINT NOT NULL,
    min_age INT NOT NULL,
    max_age INT NOT NULL,
    pref_genders TEXT NOT NULL,
    description TEXT NOT NULL,
    is_open BOOLEAN NOT NULL,
    initiated_on TIMESTAMP NOT NULL
);
-- Copy the Events table
\copy Events FROM '/home/rbors/Documents/app_project/data/Events.csv' DELIMITER ',' CSV HEADER NULL 'NULL';

-- create Matches table
CREATE TABLE Matches (
    event_id UUID NOT NULL REFERENCES Events(event_id),
    creator UUID NOT NULL REFERENCES Users(UID),
    participant UUID NOT NULL REFERENCES Users(UID),
    match BOOLEAN NOT NULL,
    chat_id UUID NOT NULL,
    chat_block TEXT NOT NULL
);
-- Copy the Matches table
\copy Matches FROM '/home/rbors/Documents/app_project/data/Matches.csv' DELIMITER ',' CSV HEADER NULL 'NULL';

-- create Chats table
CREATE TABLE Chats (
    chat_id UUID NOT NULL,
    chat_text TEXT NOT NULL,
    datetime TIMESTAMP NOT NULL,
    sender UUID NOT NULL REFERENCES Users(UID),
    recipient UUID NOT NULL REFERENCES Users(UID),
    PRIMARY KEY (chat_id, datetime)
);
-- Copy the Chats table
\copy Chats FROM '/home/rbors/Documents/app_project/data/Chats.csv' DELIMITER ',' CSV HEADER NULL 'NULL';
