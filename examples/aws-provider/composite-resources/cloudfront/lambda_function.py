import os
import json
import boto3
from Crypto.PublicKey import RSA
from datetime import datetime

def count_public_keys_in_key_group(cloudfront_client, key_group_id):
    # 获取 Key Group 的详细信息
    response = cloudfront_client.get_key_group(Id=key_group_id)
    key_group_config = response['KeyGroup']['KeyGroupConfig']

    # 返回 Key Group 中的公钥数量
    return len(key_group_config['Items'])

def delete_public_key(cloudfront_client, public_key_id, etag):
    # 删除指定的公钥
    cloudfront_client.delete_public_key(Id=public_key_id, IfMatch=etag)

def disassociate_public_key_from_key_group(cloudfront_client, key_group_id, public_key_id):
    # 从 Key Group 中取消关联公钥
    response = cloudfront_client.get_key_group(Id=key_group_id)
    key_group_config = response['KeyGroup']['KeyGroupConfig']
    key_group_config['Items'].remove(public_key_id)
    
    # 更新 Key Group 配置
    response = cloudfront_client.update_key_group(
        Id=key_group_id,
        KeyGroupConfig=key_group_config,
        IfMatch=response['ETag']
    )

def lambda_handler(event,context):
    # 创建 CloudFront 客户端
    cloudfront_client = boto3.client('cloudfront')

    # 生成 RSA 密钥对
    key = RSA.generate(2048)
    private_key = key.export_key()
    public_key = key.publickey().export_key()

    # 生成唯一的字符串+时间戳
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    caller_reference = f'my-public-key-{timestamp}'
    name = f'MyPublicKey-{timestamp}'

    # 将公钥添加到 CloudFront 的 Public Keys 中
    response = cloudfront_client.create_public_key(
        PublicKeyConfig={
            'CallerReference': caller_reference,
            'Name': name,
            'EncodedKey': public_key.decode('utf-8')
        }
    )

    # 获取生成的公钥 ID
    public_key_id = response['PublicKey']['Id']

    # 检查 Key Group 中的公钥数量
    #key_group_id = '824a1826-225b-404c-9872-575c37e470d7'
    key_group_id = os.environ['KEY_GROUP_ID']
    current_count = count_public_keys_in_key_group(cloudfront_client, key_group_id)
    if current_count >= 5:
        # 如果公钥数量已达上限，删除最早的公钥
        response = cloudfront_client.get_key_group(Id=key_group_id)
        key_group_config = response['KeyGroup']['KeyGroupConfig']
        earliest_public_key_id = key_group_config['Items'][0]
        
        # 取消最早公钥与 Key Group 的关联
        disassociate_public_key_from_key_group(cloudfront_client, key_group_id, earliest_public_key_id)
        
        # 删除最早的公钥
        response = cloudfront_client.get_public_key_config(Id=earliest_public_key_id)
        etag = response['PublicKeyConfig']['ETag']
        delete_public_key(cloudfront_client, earliest_public_key_id, etag)

    # 将新的公钥添加到 Key Group 中
    response = cloudfront_client.get_key_group(Id=key_group_id)
    key_group_config = response['KeyGroup']['KeyGroupConfig']
    key_group_config['Items'].append(public_key_id)

    # 更新 Key Group 配置
    response = cloudfront_client.update_key_group(
        Id=key_group_id,
        KeyGroupConfig=key_group_config,
        IfMatch=response['ETag']
    )

    return {
        'statusCode': 200,
        'body': json.dumps('公钥已生成并追加到现有 Key Group 中')
    }