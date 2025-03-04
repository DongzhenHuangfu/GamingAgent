import time
import os
import pyautogui
import numpy as np

from tools.utils import encode_image, log_output, get_annotate_img
from tools.serving.api_providers import anthropic_completion, openai_completion, gemini_completion
import re
import json

CACHE_DIR = "cache/boxxel"

def log_move_and_thought(move, thought, latency):
    """
    Logs the move and thought process into a log file inside the cache directory.
    """
    log_file_path = os.path.join(CACHE_DIR, "boxxel_moves.log")
    
    log_entry = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Move: {move}, Thought: {thought}, Latency: {latency:.2f} sec\n"
    
    try:
        with open(log_file_path, "a") as log_file:
            log_file.write(log_entry)
    except Exception as e:
        print(f"[ERROR] Failed to write log entry: {e}")

def boxxel_read_worker(system_prompt, api_provider, model_name, image_path):
    base64_image = encode_image(image_path)
    model_name = "gpt-4-turbo"


    
    # Construct prompt for LLM
    prompt = (
        "Extract the Boxxel board layout from the provided image."
        "Use the existing unique IDs in the image to identify each item type. "
        "For each ID, recognize the corresponding item based on item color and shape. "
        "Strictly format the output as: **ID: item type (row, column)**. "
        "Each row should reflect the board layout. "
        "Item include:  red wall, yello box, white destination, yellow ground, dark floor, player"
        "Example format: \n1: wall (0, 0) | 2: player(0, 1)| 3: dock(0, 2)... \n8: floor (1,0) | 9: box (1, 1)| 10: floor (1, 2)"
    
    )

    
    
    # Call LLM API based on provider
    if api_provider == "anthropic":
        response = anthropic_completion(system_prompt, model_name, base64_image, prompt)
    elif api_provider == "openai":
        response = openai_completion(system_prompt, model_name, base64_image, prompt)
    elif api_provider == "gemini":
        response = gemini_completion(system_prompt, model_name, base64_image, prompt)
    else:
        raise NotImplementedError(f"API provider: {api_provider} is not supported.")
    
    # Process response and format as structured board output
    structured_board = response.strip()
    
    # Generate final text output
    final_output = "\nBoxxel Board Representation:\n" + structured_board

    return final_output


def boxxel_worker(system_prompt, api_provider, model_name, prev_response=""):
    """
    1) Captures a screenshot of the current game state.
    2) Calls an LLM to generate PyAutoGUI code for the next move.
    3) Logs latency and the generated code.
    """
    # Capture a screenshot of the current game state.
    screen_width, screen_height = pyautogui.size()
    region = (0, 150, screen_width // 64 * 30, screen_height // 64 * 35)
    
    screenshot = pyautogui.screenshot(region=region)
    screenshot_path = "boxxel_screenshot.png"

    screenshot.save(screenshot_path)
    get_annotate_img('cache/boxxel/boxxel_screenshot.png', crop_left=450, crop_right=575, crop_top=60, crop_bottom=170, grid_rows=8, grid_cols=8, cache_dir = CACHE_DIR)


    table = boxxel_read_worker(system_prompt, api_provider, model_name, screenshot_path)

    prompt = (
        f"Here is the layout of the Boxxel board: {table}\n\n"

        "Please carefully analyze the boxxel table corresponding to the input image. Figure out next best move."
        "Please generate next move for this boxxel game."
        "## STRICT OUTPUT FORMAT ##\n"
        "- Respond in this format:\n"
        'move: up/down/left/right/restart/unmove, thought: "(explaination)"**\n\n'
        "you are the worker. You can move up , down, left, right."
    )



        # "### Output Format ###\n"
        # "move: <direction>, thought: <brief reasoning>\n\n"
        # "Directions: 'up', 'down', 'left', 'right', 'restart', 'unmove' (undo the last move).\n\n"
        # "Example output: move: right, thought: Positioning the player to access other boxes and docks for future moves."
    

    base64_image = encode_image(screenshot_path)
    base64_image = None
    start_time = time.time()

    print(f"Calling {model_name} api...")
    # Call the LLM API based on the selected provider.
    if api_provider == "anthropic":
        response = anthropic_completion(system_prompt, model_name, base64_image, prompt)
    elif api_provider == "openai":
        response = openai_completion(system_prompt, model_name, base64_image, prompt)
    elif api_provider == "gemini":
        response = gemini_completion(system_prompt, model_name, base64_image, prompt)
    else:
        raise NotImplementedError(f"API provider: {api_provider} is not supported.")

    latency = time.time() - start_time

    print(f"check response: {response}")

    match = re.search(r'move:\s*(\w+),\s*thought:\s*(.*)', response, re.IGNORECASE)
    move = match.group(1).strip()
    thought = match.group(2).strip()

    def perform_move(move):
        key_map = {
            "up": "up",
            "down": "down",
            "left": "left",
            "right": "right",
            "restart": 'R',
            "unmove": 'D'
        }
        if move in key_map:
            pyautogui.press(key_map[move])
            print(f"Performed move: {move}")
        else:
            print(f"[WARNING] Invalid move: {move}")

    if move is not None:
        perform_move(move)
        # Log move and thought
        log_output(
            "boxxel_worker",

            f"[INFO] Move executed: ({move}) | Thought: {thought} | Latency: {latency:.2f} sec",
            "boxxel"
        )

    return response