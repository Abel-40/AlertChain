                cache_ttl = int(duration * 3600)  # TTL based on duration (1 day = 3600 seconds)
                # Minimum 5 minutes, maximum 24 hours
                cache_ttl = max(300, min(cache_ttl, 86400))