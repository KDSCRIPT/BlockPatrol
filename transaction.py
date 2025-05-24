import asyncio
import json
import time
import requests
import os
import subprocess
from aptos_sdk.account import Account, AccountAddress
from aptos_sdk.async_client import RestClient
from aptos_sdk.transactions import (
    EntryFunction, 
    TransactionArgument, 
    TransactionPayload, 
    RawTransaction
)
from aptos_sdk.account import Account
from aptos_sdk.bcs import Serializer

NODE_URL = "http://127.0.0.1:8080/v1"  # Default Aptos localnet URL
FAUCET_URL = "http://127.0.0.1:8081/mint"  # Default localnet faucet URL

async def fund_account(address: str, amount: int = 100_000_000):
    params = {"address": address, "amount": amount}
    response = requests.post(FAUCET_URL, params=params)
    if response.status_code == 200:
        print(f"Funded account {address} with {amount} coins.")
    else:
        print(f"Failed to fund account {address}: {response.text}")
    # Wait a bit for the faucet to process
    time.sleep(1)

async def store_json(client, account, json_string, module_address):
    # Check if module exists before attempting to use it
    try:
        modules = await client.account_modules(module_address)
        module_exists = any(module["abi"]["name"] == "json_storage" for module in modules)
        if not module_exists:
            print(f"Module 'json_storage' not found at address {module_address}. Aborting transaction.")
            return None
    except Exception as e:
        print(f"Error checking module existence: {e}")
        return None
        
    entry_function = EntryFunction.natural(
        f"{module_address}::json_storage",
        "store_json",
        [],
        [TransactionArgument(json_string, Serializer.str)]
    )
    
    try:
        signed_transaction = await client.create_bcs_signed_transaction(
            account,
            TransactionPayload(entry_function)
        )
        tx_hash = await client.submit_bcs_transaction(signed_transaction)
        print(f"Transaction submitted: {tx_hash}")
        await client.wait_for_transaction(tx_hash)
        print(f"JSON stored successfully in transaction: {tx_hash}")
        return tx_hash
    except Exception as e:
        print(f"Transaction error: {e}")
        return None

async def get_json(client, account_address, module_address):
    try:
        resources = await client.account_resources(account_address)
        for resource in resources:
            if resource['type'] == f"{module_address}::json_storage::JSONStorage":
                json_string = resource['data']['data']
                return json.loads(json_string)
        print(f"No JSON storage found for address {account_address}")
        return None
    except Exception as e:
        print(f"Error retrieving JSON data: {e}")
        return None

async def publish_module(account):
    """Publish the Move module with improved error handling"""
    try:
        # Save private key in hex format (just the bytes, no 0x prefix)
        private_key_hex = account.private_key.hex()
        temp_key_path = "temp_private_key.txt"
        with open(temp_key_path, "w") as f:
            f.write(private_key_hex)
            
        print(f"Private key saved to {temp_key_path}")
        
        # First, compile the module
        print("Compiling Move module...")
        compile_cmd = [
            "aptos", "move", "compile",
            "--package-dir", ".",
            "--named-addresses", f"my_addr={account.address()}"
        ]
        compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)
        print(f"Compile stdout: {compile_result.stdout}")
        if compile_result.stderr:
            print(f"Compile stderr: {compile_result.stderr}")
        
        if compile_result.returncode != 0:
            print("Compilation failed. Aborting.")
            return False
            
        # Then, publish the module
        print("Publishing Move module...")
        publish_cmd = [
            "aptos", "move", "publish",
            "--assume-yes",
            "--private-key-file", temp_key_path,  # Use --private-key-file instead of --private-key
            "--url", NODE_URL,
            "--package-dir", ".",                 # Specify package directory
            "--named-addresses", f"my_addr={account.address()}"
        ]
        
        publish_result = subprocess.run(publish_cmd, capture_output=True, text=True)
        print(f"Publish stdout: {publish_result.stdout}")
        if publish_result.stderr:
            print(f"Publish stderr: {publish_result.stderr}")
            
        # Clean up the private key file
        if os.path.exists(temp_key_path):
            os.remove(temp_key_path)
            print(f"Removed temporary private key file: {temp_key_path}")
            
        if "Error" in publish_result.stdout or publish_result.returncode != 0:
            print("Module publication failed")
            return False
            
        print("Module published successfully")
        return True
    except Exception as e:
        print(f"Error during module publication: {e}")
        # Clean up the private key file in case of exception
        if os.path.exists(temp_key_path):
            os.remove(temp_key_path)
        return False

async def main():
    client = RestClient(NODE_URL)
    # Generate two new accounts
    # private_key_hex = "87e0b0850ddba009395ed6cf523d9d93fe26b1a61e9e28311f31f07d3df1d520"
    # private_key_bytes = bytes.fromhex(private_key_hex)

    # # Create account from private key
    # account1 = Account.load_key(private_key_bytes)


    # account1 = Account.generate()
    # account2 = Account.generate()

    # # print(f"Account 1 address: {account1.address()}")
    # print(f"Account 1 private key (hex): {account1.private_key.hex()}")
    # print(f"Account 2 private key (hex): {account2.private_key.hex()}")
    # print(f"Account 1 address: {account1.address()}")
    # print(f"Account 2 address: {account2.address()}")
    private_key_bytes = bytes.fromhex("ba5ea18121f2e4e54eec3e3973a4472376ec0adf3be7cf6138a861405a7e65be")
    account1 = Account.load_key(private_key_bytes)
    private_key_bytes = bytes.fromhex("df54af2e1110f935b92e5b489e5a884330644caef1ec6c7443336ac84a603aaf")
    account2 = Account.load_key(private_key_bytes)

    print(f"Account 1 private key (hex): {account1.private_key.hex()}")
    print(f"Account 2 private key (hex): {account2.private_key.hex()}")
    print(f"Account 1 address: {account1.address()}")
    print(f"Account 2 address: {account2.address()}")

    # Fund both accounts
    await fund_account(str(account1.address()))
    await fund_account(str(account2.address()))

    # Publish the Move module from account1
    module_published = await publish_module(account1)
    
    if not module_published:
        print("Exiting due to module publication failure")
        return
        
    # Use the new module address
    module_address = str(account1.address())
    
    # Pause to allow blockchain to process the module publication
    print("Waiting for module to be available...")
    time.sleep(5)

    # Check if the module is available before proceeding
    try:
        modules = await client.account_modules(module_address)
        module_exists = any(module["abi"]["name"] == "json_storage" for module in modules)
        if not module_exists:
            print(f"Module 'json_storage' not found. You may need to check your Move code.")
            return
        print("Module verified on chain. Proceeding with transactions.")
    except Exception as e:
        print(f"Error verifying module: {e}")
        return

    # Create and store JSON data
    json_data = {
        "name": "Example Data",
        "timestamp": int(time.time()),
        "attributes": {
            "property1": "value1",
            "property2": 42,
            "isActive": True
        },
        "metadata": {
            "creator": str(account1.address()),
            "version": "1.0"
        }
    }
    json_string = json.dumps(json_data)
    tx_hash = await store_json(client, account1, json_string, module_address=module_address)
    
    if tx_hash:
        # If transaction was successful, continue with operations
        retrieved_data = await get_json(client, account1.address(), module_address=module_address)
        print(f"Retrieved data: {retrieved_data}")
        
        json_data["attributes"]["property2"] = 99
        json_data["timestamp"] = int(time.time())
        updated_json = json.dumps(json_data)
        await store_json(client, account1, updated_json, module_address=module_address)
        
        retrieved_updated = await get_json(client, account1.address(), module_address=module_address)
        print(f"Updated data: {retrieved_updated}")
        
        account2_data = {
            "name": "Account 2 Data",
            "timestamp": int(time.time()),
            "notes": "This is stored under a different account"
        }
        await store_json(client, account2, json.dumps(account2_data), module_address=module_address)

if __name__ == "__main__":
    asyncio.run(main())