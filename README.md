# tc-transformer

A FastAPI-based application to process test cases, leveraging GPT-4o Mini for extraction and o1-mini for code generation. This project is containerized using Docker for easy deployment and scalability.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Usage](#usage)

## Overview
`tc-transformer` is a tool designed to process test case data from Excel files and generate automated test code. It integrates with external models (e.g., GPT-4o Mini and o1-mini) and can interact with web applications for testing purposes (e.g., `saucedemo.com`). The application is built with FastAPI and deployed using Docker.

## Prerequisites
- **Docker**: Ensure Docker and Docker Compose are installed on your system.
- **Python 3.11**: Required if you want to run the app locally without Docker.
- **curl**: For testing the API endpoint (optional).
- An Excel file (`.xlsx`) containing test case data.
- Access to GPT-4o Mini and o1-mini models (API keys or deployment credentials).

## Setup
Follow these steps to get the project running:

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/tc-transformer.git
   cd tc-transformer
   ```

2. **Configure Environment Variables**
   - Create a `.env` file in the root directory based on the provided `.env.sample`.
   - Add the required API keys or credentials for:
     - GPT-4o Mini (used for extraction)
     - o1-mini (used for code generation)
   - Example `.env`:
     ```
     AZURE_OPENAI_API_BASE=your_openai_base
     AZURE_OPENAI_API_KEY=your_openai_key
     
     ```

3. **Build and Run with Docker**
   - Use Docker Compose to build and start the application:
     ```bash
     docker-compose up --build
     ```
   - This will start the FastAPI server on `http://0.0.0.0:8000`.

## Usage
Once the application is running, you can interact with it via the `/process-test-cases` endpoint.

### cURL Example
Send a POST request with an Excel file and test parameters:
```bash
curl -X POST "http://127.0.0.1:8000/process-test-cases" \
-F "file=@/path/to/your/input.xlsx" \
-F "test_url=https://www.saucedemo.com" \
-F "username=standard_user" \
-F "password=secret_sauce"
```

- **`file`**: Path to your `.xlsx` file containing test cases.
- **`test_url`**: The URL of the application under test (e.g., `https://www.saucedemo.com`).
- **`username`**: Test user credentials.
- **`password`**: Test user password.

### Expected Output
The endpoint processes the test cases and returns generated code or results based on the input data and model configurations.
