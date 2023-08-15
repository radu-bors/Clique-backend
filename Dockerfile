# Use an official Python runtime as a parent image
FROM python:3.10

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install fastapi uvicorn

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Copy SSL certificate and key
COPY localhost.crt /app
COPY localhost.key /app

# Run uvicorn with SSL when the container launches
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]