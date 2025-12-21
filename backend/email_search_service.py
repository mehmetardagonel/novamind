"""
Email Search Service - Unified search for Gmail and Outlook
Supports Gmail search operators and converts them to Microsoft Graph queries
"""

import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timezone
import httpx

logger = logging.getLogger(__name__)


def search_gmail(query: str, service, max_results: int = 50) -> List[Dict]:
    """
    Search Gmail using Gmail API with search operators

    Args:
        query: Gmail search query (e.g., "from:google jobs is:unread")
        service: Gmail API service instance
        max_results: Maximum results to return

    Returns:
        List of email dictionaries
    """
    try:
        from models import EmailOut
        from gmail_service import parse_message

        logger.info(f"Searching Gmail with query: {query}")

        # Search for messages
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            logger.info(f"No Gmail messages found for query: {query}")
            return []

        logger.info(f"Found {len(messages)} Gmail messages")

        # Fetch full message details
        emails = []
        for msg in messages:
            try:
                full_msg = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()

                email = parse_message(full_msg)
                if email:
                    emails.append(email.model_dump(mode='json'))
            except Exception as e:
                logger.error(f"Error parsing Gmail message {msg['id']}: {e}")
                continue

        return emails

    except Exception as e:
        logger.error(f"Error searching Gmail: {e}")
        return []


async def search_outlook(query: str, access_token: str, max_results: int = 50) -> List[Dict]:
    """
    Search Outlook using Microsoft Graph Search API

    Args:
        query: Search query (Gmail syntax will be converted)
        access_token: Microsoft Graph access token
        max_results: Maximum results to return

    Returns:
        List of email dictionaries
    """
    try:
        from query_converter import convert_gmail_to_graph_query
        from outlook_service import parse_outlook_message

        logger.info(f"Searching Outlook with query: {query}")

        # Convert Gmail query to Graph query
        graph_query = convert_gmail_to_graph_query(query)
        logger.info(f"Converted to Graph query: {graph_query}")

        # Use Microsoft Graph Search API
        search_body = {
            "requests": [{
                "entityTypes": ["microsoft.graph.message"],
                "query": {
                    "queryString": graph_query
                },
                "from": 0,
                "size": max_results
            }]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://graph.microsoft.com/v1.0/search/query",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=search_body,
                timeout=30.0
            )

            if response.status_code != 200:
                logger.error(f"Outlook search failed: {response.status_code} - {response.text}")
                return []

            data = response.json()
            hits = data.get('value', [{}])[0].get('hitsContainers', [{}])[0].get('hits', [])

            logger.info(f"Found {len(hits)} Outlook messages")

            # Parse messages
            emails = []
            for hit in hits:
                try:
                    msg = hit.get('resource', {})
                    email = parse_outlook_message(msg)
                    if email:
                        emails.append(email)
                except Exception as e:
                    logger.error(f"Error parsing Outlook message: {e}")
                    continue

            return emails

    except Exception as e:
        logger.error(f"Error searching Outlook: {e}")
        return []


async def unified_search(
    query: str,
    user_id: str,
    provider: Optional[str] = None,
    account_id: Optional[str] = None,
    max_results: int = 50
) -> List[Dict]:
    """
    Search across Gmail and/or Outlook accounts

    Args:
        query: Search query (Gmail operator syntax)
        user_id: User ID for multi-account lookup
        provider: "gmail" or "outlook" (optional - searches both if not specified)
        account_id: Specific account ID (optional)
        max_results: Maximum results per provider

    Returns:
        Combined and sorted list of emails from all searched providers
    """
    try:
        from email_account_service import email_account_service
        import asyncio
        from gmail_service import get_user_gmail_service

        # Get user's email accounts
        accounts = await email_account_service.get_all_accounts(user_id)

        if not accounts:
            logger.warning(f"No email accounts found for user {user_id}")
            return []

        # Filter accounts by provider and account_id if specified
        if provider:
            accounts = [acc for acc in accounts if acc.get('provider') == provider]

        if account_id:
            accounts = [acc for acc in accounts if acc.get('id') == account_id]

        if not accounts:
            logger.warning(f"No matching accounts found for user {user_id}")
            return []

        logger.info(f"Searching {len(accounts)} account(s)")

        # Search all accounts concurrently
        search_tasks = []

        for account in accounts:
            provider_type = account.get('provider', 'gmail')

            if provider_type == 'gmail':
                # Gmail search (sync, so wrap in executor)
                async def search_gmail_async(acc=account):
                    service = await get_user_gmail_service(user_id, acc['id'])
                    # Run sync search_gmail in executor
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        None,
                        lambda: search_gmail(query, service, max_results)
                    )

                task = search_gmail_async()
                search_tasks.append(('gmail', account, task))

            elif provider_type == 'outlook':
                # Outlook search (async)
                token = account.get('access_token')
                if token:
                    task = search_outlook(query, token, max_results)
                    search_tasks.append(('outlook', account, task))

        # Wait for all searches to complete
        all_emails = []
        for provider_type, account, task in search_tasks:
            try:
                results = await task

                # Add account metadata to each email
                for email in results:
                    email['account_id'] = account['id']
                    email['account_email'] = account.get('email_address')
                    email['provider'] = provider_type

                all_emails.extend(results)
                logger.info(f"Got {len(results)} results from {provider_type} account {account.get('email_address')}")

            except Exception as e:
                logger.error(f"Error searching {provider_type} account {account.get('id')}: {e}")
                continue

        # Sort by date (most recent first)
        all_emails.sort(
            key=lambda x: x.get('date') or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )

        logger.info(f"Total search results: {len(all_emails)}")
        return all_emails

    except Exception as e:
        logger.error(f"Error in unified search: {e}")
        return []
