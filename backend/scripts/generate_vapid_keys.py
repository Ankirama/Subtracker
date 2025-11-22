#!/usr/bin/env python3
"""
Generate VAPID keys for Web Push Notifications.
Run this script once to generate VAPID keys and add them to your .env file.
"""
from py_vapid import Vapid
import base64

def generate_vapid_keys():
    """Generate VAPID public and private keys."""
    vapid = Vapid()
    vapid.generate_keys()

    # Get keys in URL-safe base64 format
    # py-vapid stores keys internally, we need to export them
    from cryptography.hazmat.primitives import serialization

    # Get private key bytes
    private_key_pem = vapid.private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Get public key bytes in raw format
    public_key_bytes = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )

    # Convert to URL-safe base64
    public_key = base64.urlsafe_b64encode(public_key_bytes).decode('utf-8').rstrip('=')
    private_key = private_key_pem.decode('utf-8')

    print("=" * 80)
    print("VAPID Keys Generated Successfully!")
    print("=" * 80)
    print("\nPublic Key:")
    print(f"  {public_key}")
    print("\nPrivate Key:")
    print(f"  {private_key}")
    print("\n" + "=" * 80)
    print("Add these to your .env file:")
    print("=" * 80)
    print(f"\nVAPID_PUBLIC_KEY={public_key}")
    print(f"VAPID_PRIVATE_KEY={private_key}")
    print("VAPID_CLAIM_EMAIL=mailto:your-email@example.com")
    print("\n" + "=" * 80)
    print("IMPORTANT: Keep the private key secure and never commit it to version control!")
    print("=" * 80)

if __name__ == "__main__":
    generate_vapid_keys()
