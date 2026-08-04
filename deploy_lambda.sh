#!/bin/bash
# Usage: ./deploy_lambda.sh [--new]
#   Default: updates the existing Lambda function code.
#   --new: creates the Lambda function for the first time.
#
# Bundles app/requirements.txt dependencies directly into the deploy zip
# (built in a disposable ./lambda_build/ dir, never touching the tracked
# app/ source tree) rather than relying on a separately-maintained Lambda
# layer. boto3 is skipped since it's already provided by the Lambda
# runtime; pyngrok is local-dev-only.
#
# Only git-tracked files under app/ are deployed (via `git archive`), so
# uncommitted changes are never shipped - commit first.

set -e

FUNCTION_NAME="CBFunction"
BUILD_DIR="lambda_build"
ZIP_FILE_PATH="cbpackage.zip"
HANDLER="lambda_app.lambda_handler"
NEW=false

for arg in "$@"; do
  case $arg in
    --new) NEW=true ;;
  esac
done

echo "Copying git-tracked app files..."
rm -rf $BUILD_DIR $ZIP_FILE_PATH
mkdir -p $BUILD_DIR
git -C app archive HEAD | tar -x -C $BUILD_DIR

echo "Installing dependencies..."
grep -v -E '^(boto3|pyngrok)' app/requirements.txt > /tmp/cb-deploy-requirements.txt
# Lambda runs Linux/Python 3.8 regardless of what this is run from (e.g. an
# ARM Mac on Python 3.13) - pin the wheel platform/version explicitly so we
# never accidentally bundle a binary built for the wrong target.
pip install \
  --platform manylinux2014_x86_64 \
  --target $BUILD_DIR \
  --python-version 3.8 \
  --implementation cp \
  --only-binary=:all: \
  -r /tmp/cb-deploy-requirements.txt --quiet
rm /tmp/cb-deploy-requirements.txt

echo "Packaging..."
(cd $BUILD_DIR && zip -rq ../$ZIP_FILE_PATH .)

if [ "$NEW" = true ]; then
  echo "Creating new Lambda function..."
  aws lambda create-function \
    --profile mcb7 \
    --region us-east-1 \
    --function-name $FUNCTION_NAME \
    --runtime python3.8 \
    --role arn:aws:iam::239460480281:role/cb-dashboard-data-store-lambda-role \
    --handler $HANDLER \
    --zip-file fileb://$ZIP_FILE_PATH
else
  echo "Updating Lambda function code..."
  aws lambda update-function-code \
    --profile mcb7 \
    --region us-east-1 \
    --function-name $FUNCTION_NAME \
    --zip-file fileb://$ZIP_FILE_PATH
fi

rm -rf $BUILD_DIR $ZIP_FILE_PATH
