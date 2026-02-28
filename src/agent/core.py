"""
agent/core.py
-------------
Initialises the Gemini client and runs the interactive CLI chat loop.

Exception hierarchy used (google-genai SDK):
    google.genai.errors.ClientError  – 4xx responses: auth (401), permission (403),
                                       quota / rate-limit (429), bad request (400)
    google.genai.errors.ServerError  – 5xx responses: service unavailable, etc.
    google.genai.errors.APIError     – parent of both; catch-all for API-level errors
"""

import logging
import os

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

from agent.tools import (
    get_view_schemas,
    query_supplier_purchases_view,
    query_customer_sales_view,
    query_inventory_status_view,
)

logger = logging.getLogger(__name__)

# HTTP status codes returned by Gemini's ClientError
_HTTP_UNAUTHENTICATED  = 401
_HTTP_PERMISSION_DENIED = 403
_HTTP_QUOTA_EXCEEDED   = 429


# ── Agent factory ─────────────────────────────────────────────────────────────

def create_agent():
    """Initialises the Gemini client and returns ``(client, chat)``.

    The caller **must** hold a reference to *client* for as long as the chat
    session is used.  Letting it go out of scope closes the underlying HTTP
    connection pool and causes ``RuntimeError: Cannot send a request, as the
    client has been closed`` on the next ``chat.send_message()`` call.

    Raises:
        ClientError: For auth (401), permission (403), quota (429), or bad-request errors.
        ServerError: If the Gemini service is temporarily unavailable (5xx).
        APIError:    For any other API-level failure.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.warning(
            "GOOGLE_API_KEY environment variable is not set. "
            "The Gemini client will likely refuse to connect."
        )
    else:
        # Log only the key prefix so we know it loaded without exposing the secret.
        logger.debug("GOOGLE_API_KEY loaded (prefix: %s…).", api_key[:6])

    tools = [
        get_view_schemas,
        query_supplier_purchases_view,
        query_customer_sales_view,
        query_inventory_status_view,
    ]

    system_instruction = """
    You are an expert Data Retrieval Agent for a company's ERP database.
    Your goal is to answer user queries accurately by pulling data from the database.

    CRITICAL INSTRUCTIONS:
    1. NEVER GUESS column names. Your FIRST STEP should ALWAYS be to call `get_view_schemas()`
       to see the exact column names available in the 3 semantic views.
    2. ONCE you know the schema, call the appropriate query tool (e.g., `query_supplier_purchases_view`).
    3. The query tools ONLY ACCEPT a `select_clause` and a `where_clause`.
       - Do NOT write 'SELECT' or 'WHERE' in your arguments.
       - Example select_clause: "supplier_name, SUM(line_total) as total"
       - Example where_clause: "order_status = 'DELIVERED' GROUP BY supplier_name"
    4. If you need data from multiple views to answer a question, you may make sequential tool calls.
    5. After retrieving the data, format it into a clear, natural language answer for the user.
       Do not just spit out the JSON.
    """

    config = types.GenerateContentConfig(
        tools=tools,
        system_instruction=system_instruction,
        temperature=0.1,  # Keep it deterministic for SQL writing
    )

    logger.debug("Creating Gemini chat session with model 'gemini-2.5-flash'.")

    try:
        client = genai.Client()
        chat = client.chats.create(model="gemini-2.5-flash", config=config)
        logger.info("Gemini chat session created successfully.")
        return client, chat  # caller must keep `client` alive

    except ClientError as exc:
        # 4xx — client-side errors we can describe specifically.
        if exc.code == _HTTP_UNAUTHENTICATED:
            logger.error(
                "Authentication failed (HTTP 401) — GOOGLE_API_KEY is missing or invalid: %s", exc
            )
        elif exc.code == _HTTP_PERMISSION_DENIED:
            logger.error(
                "Permission denied (HTTP 403) — the API key may not have access "
                "to the requested model: %s", exc
            )
        elif exc.code == _HTTP_QUOTA_EXCEEDED:
            logger.error(
                "Quota or rate-limit exceeded (HTTP 429) — wait and retry: %s", exc
            )
        else:
            logger.error(
                "Gemini client error (HTTP %s) during agent initialisation: %s",
                exc.code, exc,
            )
        raise

    except ServerError as exc:
        logger.error(
            "Gemini server error (HTTP %s) — the service may be temporarily "
            "unavailable. Try again in a moment: %s",
            exc.code, exc,
        )
        raise

    except APIError as exc:
        # Parent class — any other API-level failure not covered above.
        logger.error("Gemini API error during client initialisation: %s", exc)
        raise

    except Exception:
        # Truly unexpected — log the full traceback so nothing is hidden.
        logger.exception("Unexpected non-API error while creating the Gemini agent.")
        raise


# ── Chat loop ─────────────────────────────────────────────────────────────────

def chat_loop():
    """Runs the interactive CLI loop."""
    print("=" * 50)
    print("Agentic Chat PoC — Semantic View SQL Agent initialised.")
    print("Type 'exit' or 'quit' to end the session.")
    print("=" * 50)

    logger.info("chat_loop() started.")

    # ── Initialise the agent ─────────────────────────────────────────────────
    try:
        client, chat = create_agent()  # keep `client` referenced so httpx stays open
    except ClientError as exc:
        if exc.code == _HTTP_UNAUTHENTICATED:
            print("\n[ERROR] Authentication failed. Please set a valid GOOGLE_API_KEY in your .env file.")
        elif exc.code == _HTTP_PERMISSION_DENIED:
            print("\n[ERROR] Permission denied. Verify your API key has access to this model.")
        elif exc.code == _HTTP_QUOTA_EXCEEDED:
            print("\n[ERROR] API quota exceeded. Please wait before retrying.")
        else:
            print(f"\n[ERROR] Gemini client error during startup (HTTP {exc.code}). "
                  "Check logs/agent.log for details.")
        logger.error("chat_loop() exiting early — ClientError at startup.")
        return
    except ServerError:
        print("\n[ERROR] The Gemini service is currently unavailable. Try again in a moment.")
        logger.error("chat_loop() exiting early — ServerError (5xx) at startup.")
        return
    except APIError:
        print("\n[ERROR] Gemini API error during startup. Check logs/agent.log for details.")
        logger.error("chat_loop() exiting early — APIError at startup.")
        return
    except Exception:
        print("\n[ERROR] Unexpected error during agent initialisation. Check logs/agent.log for details.")
        logger.exception("chat_loop() exiting early — unexpected error during create_agent().")
        return

    # ── Main query loop ──────────────────────────────────────────────────────
    while True:
        try:
            user_input = input("\nUser Query: ")

            if user_input.lower() in ("exit", "quit"):
                logger.info("User requested exit.")
                break

            if not user_input.strip():
                logger.debug("Empty input received — skipping.")
                continue

            logger.debug("Sending user query to Gemini: %r", user_input)
            print("\nAgent is thinking and querying tools…")

            response = chat.send_message(user_input)

            logger.debug("Raw response text: %r", response.text)
            print("\nAgent Response:")
            print(response.text)

        except KeyboardInterrupt:
            print("\nExiting…")
            logger.info("Chat loop interrupted by user (Ctrl-C).")
            break

        except ClientError as exc:
            if exc.code == _HTTP_QUOTA_EXCEEDED:
                print("\n[WARNING] API quota / rate-limit hit. Please wait before retrying.")
                logger.warning("Gemini quota exceeded (HTTP 429): %s", exc)
            else:
                print(f"\n[ERROR] Gemini client error while processing your query (HTTP {exc.code}). "
                      "Check logs/agent.log for details.")
                logger.error("Gemini ClientError during send_message (HTTP %s): %s",
                             exc.code, exc, exc_info=True)

        except ServerError as exc:
            print("\n[ERROR] Gemini service error. The service may be temporarily unavailable.")
            logger.error("Gemini ServerError during send_message (HTTP %s): %s",
                         exc.code, exc, exc_info=True)

        except APIError as exc:
            print(f"\n[ERROR] Gemini API error while processing your query: {exc}")
            logger.error("Gemini APIError during send_message: %s", exc, exc_info=True)

        except Exception:
            print("\n[ERROR] An unexpected error occurred. Check logs/agent.log for the full trace.")
            logger.exception("Unexpected error while processing user query.")

    logger.info("chat_loop() finished.")
