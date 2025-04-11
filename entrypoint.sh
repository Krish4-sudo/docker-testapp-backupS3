#!/bin/bash

# Mount the S3 bucket
echo "${AWS_ACCESS_KEY_ID}:${AWS_SECRET_ACCESS_KEY}" > /root/.passwd-s3fs
chmod 600 /root/.passwd-s3fs

s3fs ${S3_BUCKET} ${S3_MOUNT_POINT} -o passwd_file=/root/.passwd-s3fs -o allow_other -o use_path_request_style

# Start your application
exec "$@"



# command which will run inside container bash to setup the s3fs sync with your host machine