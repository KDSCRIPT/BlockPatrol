module my_addr::json_storage {
    use std::string::{Self, String};
    use std::signer;
    
    /// Error codes
    const ENO_DATA_STORED: u64 = 1;
    
    /// Resource to store JSON string data
    struct JSONStorage has key {
        data: String
    }
    
    /// Initialize the module - called during publishing
    fun init_module(account: &signer) {
        let empty = string::utf8(b"{}");
        move_to(account, JSONStorage { data: empty });
    }
    
    /// Store JSON data under the signer's account
    public entry fun store_json(account: &signer, json_data: String) acquires JSONStorage {
        let addr = signer::address_of(account);
        
        // Create storage if it doesn't exist yet
        if (!exists<JSONStorage>(addr)) {
            move_to(account, JSONStorage { data: json_data });
        } else {
            // Update existing storage
            let storage = borrow_global_mut<JSONStorage>(addr);
            storage.data = json_data;
        }
    }
    
    /// Retrieve JSON data
    public fun get_json(addr: address): String acquires JSONStorage {
        assert!(exists<JSONStorage>(addr), ENO_DATA_STORED);
        let storage = borrow_global<JSONStorage>(addr);
        storage.data
    }
    
    /// Check if JSON storage exists for an address
    public fun has_json(addr: address): bool {
        exists<JSONStorage>(addr)
    }
}