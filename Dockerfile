# Use an official Python runtime as a parent image
FROM python:3.8-slim

# Set the working directory in the container to /code
WORKDIR /code

# Copy the current directory contents into the container at /code
COPY . /code

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir --index-url https://test.pypi.org/simple/ pyssem==0.1.dev151


# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variable
ENV FLASK_ENV=development

# Run main.py when the container launches
CMD ["flask", "run", "--host=0.0.0.0"]