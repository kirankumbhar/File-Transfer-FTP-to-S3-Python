import math
import time
import io
import boto3
import paramiko

S3_BUCKET_NAME = "example-bucket"

FTP_HOST = "ftp.example.com"
FTP_PORT = 22
FTP_USERNAME = "john.doe"
FTP_PASSWORD = "XXXX"

CHUNK_SIZE = 6291456


def open_ftp_connection(ftp_host, ftp_port, ftp_username, ftp_password):
    """
    Opens ftp connection and returns connection object

    """
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    try:
        transport = paramiko.Transport(ftp_host, ftp_port)
    except Exception as e:
        return "conn_error"
    try:
        transport.connect(username=ftp_username, password=ftp_password)
    except Exception as identifier:
        return "auth_error"
    ftp_connection = paramiko.SFTPClient.from_transport(transport)
    return ftp_connection


def transfer_chunk_from_ftp_to_s3(
    ftp_file,
    s3_connection,
    multipart_upload,
    bucket_name,
    ftp_file_path,
    s3_file_path,
    part_number,
    chunk_size,
):
    start_time = time.time()
    chunk = ftp_file.read(int(chunk_size))
    part = s3_connection.upload_part(
        Bucket=bucket_name,
        Key=s3_file_path,
        PartNumber=part_number,
        UploadId=multipart_upload["UploadId"],
        Body=chunk,
    )
    end_time = time.time()
    total_seconds = end_time - start_time
    print(
        "speed is {} kb/s total seconds taken {}".format(
            math.ceil((int(chunk_size) / 1024) / total_seconds), total_seconds
        )
    )
    part_output = {"PartNumber": part_number, "ETag": part["ETag"]}
    return part_output


def transfer_file_from_ftp_to_s3(
    bucket_name, ftp_file_path, s3_file_path, ftp_username, ftp_password, chunk_size
):
    ftp_connection = open_ftp_connection(
        FTP_HOST, int(FTP_PORT), ftp_username, ftp_password
    )
    ftp_file = ftp_connection.file(ftp_file_path, "r")
    s3_connection = boto3.client("s3")
    ftp_file_size = ftp_file._get_size()
    try:
        s3_file = s3_connection.head_object(Bucket=bucket_name, Key=s3_file_path)
        if s3_file["ContentLength"] == ftp_file_size:
            print("File Already Exists in S3 bucket")
            ftp_file.close()
            return
    except Exception as e:
        pass
    if ftp_file_size <= int(chunk_size):
        # upload file in one go
        print("Transferring complete File from FTP to S3...")
        ftp_file_data = ftp_file.read()
        ftp_file_data_bytes = io.BytesIO(ftp_file_data)
        s3_connection.upload_fileobj(ftp_file_data_bytes, bucket_name, s3_file_path)
        print("Successfully Transferred file from FTP to S3!")
        ftp_file.close()

    else:
        print("Transferring File from FTP to S3 in chunks...")
        # upload file in chunks
        chunk_count = int(math.ceil(ftp_file_size / float(chunk_size)))
        multipart_upload = s3_connection.create_multipart_upload(
            Bucket=bucket_name, Key=s3_file_path
        )
        parts = []
        for i in range(chunk_count):
            print("Transferring chunk {}...".format(i + 1))
            part = transfer_chunk_from_ftp_to_s3(
                ftp_file,
                s3_connection,
                multipart_upload,
                bucket_name,
                ftp_file_path,
                s3_file_path,
                i + 1,
                chunk_size,
            )
            parts.append(part)
            print("Chunk {} Transferred Successfully!".format(i + 1))

        part_info = {"Parts": parts}
        s3_connection.complete_multipart_upload(
            Bucket=bucket_name,
            Key=s3_file_path,
            UploadId=multipart_upload["UploadId"],
            MultipartUpload=part_info,
        )
        print("All chunks Transferred to S3 bucket! File Transfer successful!")
        ftp_file.close()


if __name__ == "__main__":
    ftp_username = FTP_USERNAME
    ftp_password = FTP_PASSWORD
    ftp_file_path = str(input("Enter file path located on FTP server: "))
    s3_file_path = str(input("Enter file path to upload to s3: "))
    ftp_connection = open_ftp_connection(
        FTP_HOST, int(FTP_PORT), ftp_username, ftp_password
    )
    if ftp_connection == "conn_error":
        print("Failed to connect FTP Server!")
    elif ftp_connection == "auth_error":
        print("Incorrect username or password!")
    else:
        try:
            ftp_file = ftp_connection.file(ftp_file_path, "r")
        except Exception as e:
            print("File does not exists on FTP Server!")
        transfer_file_from_ftp_to_s3(
            S3_BUCKET_NAME,
            ftp_file_path,
            s3_file_path,
            ftp_username,
            ftp_password,
            CHUNK_SIZE,
        )
