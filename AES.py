import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

# def aes_encrypt(key, plaintext):
#     # 使用PKCS7进行填充
#     padder = padding.PKCS7(128).padder()
#     padded_data = padder.update(plaintext) + padder.finalize()
#
#     # 初始化加密器
#     cipher = Cipher(algorithms.AES(key), modes.CBC(os.urandom(16)), backend=default_backend())
#     encryptor = cipher.encryptor()
#
#     # 加密数据
#     ciphertext = encryptor.update(padded_data) + encryptor.finalize()
#     return ciphertext

# def aes_decrypt(key, ciphertext):
#     # 初始化解密器
#     cipher = Cipher(algorithms.AES(key), modes.CBC(os.urandom(16)), backend=default_backend())
#     decryptor = cipher.decryptor()
#
#     # 解密数据
#     padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
#
#     # 移除填充
#     unpadder = padding.PKCS7(128).unpadder()
#     plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
#     return plaintext

def aes_encrypt(key, plaintext):
    # 使用PKCS7进行填充
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext) + padder.finalize()
    # 初始化加密器
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    # 加密数据
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    return encrypted_data

def aes_decrypt(key, ciphertext):
    # 初始化解密器
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()
    # 解密数据
    decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
    # 移除填充
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(decrypted_data) + unpadder.finalize()
    return plaintext
