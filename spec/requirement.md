**Role:** Expert Python Developer and AI Engineer.

**Objective:** Develop a Proof of Concept (PoC) CLI-based Agentic Chat application. The agent will process natural language queries, interact with a local database using specific tools, and return the formatted results to the user.

**Technology Stack:**
* **Language:** Python
* **Agent Framework:** Google ADK (Agent Development Kit)
* **Database:** SQLite
* **LLM:** Low-cost Gemini model (e.g., `gemini-1.5-flash`)

**Execution Steps & Constraints:**

**1. Database Design & Synthetic Data Generation:**
* Design a relational database schema centered around the concepts of Purchases, Suppliers, and Products.
* Apply database normalization principles (at least 3NF) so that the schema consists of 8 to 10 distinct tables (e.g., `Suppliers`, `Products`, `Categories`, `PurchaseOrders`, `PurchaseOrderLineItems`, etc.).
* Include a startup script or function that automatically creates the SQLite database, builds the tables, and populates them with synthetic, realistic mock data if the database does not already exist.

**2. Modular Tool Design (Strict Constraint):**
* **CRITICAL:** Do not configure the agent to write or execute complex SQL queries involving multiple `JOIN` statements across tables. 
* Instead, build the agent's capabilities using multiple, atomic Python functions (e.g., `get_supplier_data(supplier_id)`, `get_products_by_category(category_name)`, `get_recent_purchases(limit)`).
* Register these modular functions as tools using the Google ADK. The agent must orchestrate these smaller tools to gather data piece-by-piece to answer complex user questions.

**3. CLI Application Loop:**
* Implement a clean command-line interface (CLI) loop that accepts user input.
* Pass the input to the Google ADK agent to route to the appropriate tools and return the final synthesized answer to the terminal. 

**4. Documentation:**
* Treat this as a PoC. Keep documentation lightweight and straightforward. Provide basic inline comments explaining the tool logic and a simple text block explaining how to run the script.



**Example Tool Definitions for the Agent:**

Please implement the following Python functions to serve as the agent's tools. Ensure each function connects to the SQLite database, executes a simple single-table SELECT statement, and returns the data (e.g., as a dictionary or list of dictionaries). 

Do NOT write complex JOINs inside these functions. The agent must call them sequentially if it needs to connect data.

1. **Supplier Tools:**

def search_supplier_by_name(name_query: str) -> list[dict]:
    """
    Searches for a supplier by name. 
    Use this first when the user asks about a specific supplier to find their supplier_id.
    """
    pass

def get_supplier_details(supplier_id: int) -> dict:
    """
    Retrieves the full profile, contact info, and rating for a specific supplier using their exact ID.
    """
    pass
'

2. **Purchase Order Tools:**    

def get_purchase_order_by_id(order_id: int) -> dict:
    """
    Retrieves the header information for a specific purchase order (e.g., date, status, total_amount).
    """
    pass

def get_order_line_items(order_id: int) -> list[dict]:
    """
    Retrieves the individual line items for a specific purchase order.
    This is crucial for seeing exactly which products were bought in that order.
    """
    pass

3. **Product & Category Tools:**    


def get_category_name(category_id: int) -> str:
    """
    Retrieves the human-readable name for a given category_id.
    """
    pass

def get_product_name(product_id: int) -> str:
    """
    Retrieves the human-readable name for a given product_id.
    """
    pass    

**Agent execution example:**

*"What products did we order in Purchase Order #105?"*
The agent will reason through it like this:
1. "I need to look at PO #105. I'll call `get_purchase_order_line_items(po_id=105)`."
2. "The tool returned a list of `product_ids`. But the user wants to know *what* the products are, not just their IDs."
3. "I will loop through those IDs and call `get_product_details(product_id)` for each one."
4. "Now I have the product names and can answer the user."
    
**Output:** Please generate the complete, modular Python code to fulfill these requirements.




