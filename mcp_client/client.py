import asyncio
import sys

from pathlib import Path
from mcp import Client, StdioServerParameters


async def main():

    # Racine du projet
    project_root = Path(__file__).resolve().parent.parent

    # Chemin vers server.py
    server_file = project_root / "mcp_server" / "server.py"

    print("Serveur MCP :", server_file)

    # Paramètres permettant de lancer le serveur MCP
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_file)]
    )

    print("\nConnexion au serveur MCP...")


    # Le Client démarre automatiquement server.py
    async with Client(server_params) as client:

        print("Connexion MCP établie.")

        print(
            "Version du protocole :",
            client.protocol_version
        )


        # ----------------------------------------
        # LISTE DES TOOLS
        # ----------------------------------------

        tools = await client.list_tools()

        print("\n=== TOOLS DISPONIBLES ===")

        for tool in tools.tools:
            print(f"- {tool.name}")


        # ----------------------------------------
        # APPEL D'UN TOOL
        # ----------------------------------------

        print("\n=== APPEL list_open_tickets ===")

        result = await client.call_tool(
            "list_open_tickets",
            {}
        )


        if result.structured_content is not None:

            print(result.structured_content)

        else:

            for block in result.content:

                if hasattr(block, "text"):
                    print(block.text)


if __name__ == "__main__":
    asyncio.run(main())