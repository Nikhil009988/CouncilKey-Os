"""
CouncilKey-Os Computer Use Full Linux Desktop Canvas Like Agent Zero - Advanced Production
Full Linux desktop in Canvas, agent can use real GUI software, terminals, files, desktop apps inside Canvas
"""

def canvas_tools():
    return [
        {
            "name": "canvas_full_desktop",
            "description": "Full Linux desktop in Canvas, agent can use real GUI software, terminals, files, desktop apps inside Canvas - from Agent Zero",
            "how": "Agent Zero Canvas: Full Linux desktop via noVNC or similar, agent controls GUI via AT-SPI or Wayland/X11 input"
        },
        {
            "name": "canvas_file_browser",
            "description": "File browser: Explore and preview the working directory without leaving the app - from Hermes Desktop",
            "how": "File browser in Canvas"
        },
        {
            "name": "canvas_live_document_cowork",
            "description": "Live document cowork: Edit Markdown, Writer, Spreadsheet, Presentation files together instead of losing work in chat - from Agent Zero",
            "how": "Live document editing in Canvas with user"
        },
        {
            "name": "canvas_host_machine_bridge",
            "description": "Host-machine bridge via A0 CLI so same agent can work in real local repositories - from Agent Zero",
            "how": "A0 CLI connects Canvas agent to host-machine real local repos"
        },
        {
            "name": "canvas_multi_agent_cooperation",
            "description": "Multi-agent cooperation: Let agents delegate research, coding, analysis, or review tasks to focused subagents - from Agent Zero",
            "how": "Subagents for research, coding, analysis, review"
        }
    ]

if __name__ == "__main__":
    import json
    print(json.dumps(canvas_tools(), indent=2))
