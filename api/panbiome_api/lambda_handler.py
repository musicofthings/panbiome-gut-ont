"""AWS Lambda entry point. API Gateway (HTTP API) checks the Cognito token before a request gets here."""

from mangum import Mangum

from .main import app

handler = Mangum(app, lifespan="off")
