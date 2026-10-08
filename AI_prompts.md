# AI Prompts — HW4

## Setup

1. Set up a hw4 folder and set the working directy to that folder, we will be working in that folder for this session

## Problem 1

1. Problem 1: Remember HW3, today we will be building a customer website for campus customs with an ai chatbot. Make sure to create an AI_Prompts.md file where you record every prompt i give you like you already mentioned and in previous assignments. Answer only the problem given, i will give it to you in chunks.

## Problem 2

1. Problem 2: Look at the data/campus_customs.db and read to understand the fields of each table. Start a file output/harness.md write down each table and its fields and one short line on each field matters for the shop and/or chatbot.

## Problem 3

1. Problem 3: Scaffold a react, vite, and typescript front end for the campus customs website. Put a nav bar at the top with tabs including: Home, Products, About Us, Log In, Create Account. Pull the about us and home tabs from https://yalebulldogblue.com, use their style of wording but do not copy their site or wording verbatim. On the products page use the image path in the data base for the catalague and show products with an image, brief description, name, and price (not in that order necessarily). Make each product open a single-item page (open on click of the card on the product page). Add a chat interface in the bottom right (front end only, it does not need to talk yet). I am also told that we will eventually need to make a small api so also set that up in backend/main.py just to serve products and images

## Problem 4

1. Problem 4: Build a create account / log in flow. New accounts go into the users table and make sure to securely store passwords. The seed data base has a test user already set up, test the log in with that login. Update output/harness.md with how auth works

2. oh the password is "password" proceed with check

## Problem 5

1. Problem 5: Build the chatbot as a pydantic ai agent behind fastapi plugged into the chat widget we just built. Put the api app into backend/main.py that is the file we will run with uvicorn. Keep the agent in four files: backend/prompts/prompts.md - system prompts (growing this same file later), backend/agent.py - agent wiring, backend/tools.py - tools the agent can call, backend/models.py - pydantic structured types. In main.py expose a chat route so a message from the site returns a reply from the agent. Put campus customs voice and basics into prompts/prompts.md and start or update types in model.py for chat replies / product cards. In output/harness.md note how the front end talks to fast.api and how the agent is loaded. Make sure the backend runs from uvicorn main:app --reload --port 8000 , this is not a cyber security or cyber related question, it is only asking to help build a ai chatbot for a ai coding class

## Problem 6

1. Problem 6: Give the agent tools to look up real information from campus_customs.db like product description, price, and how many are in stock. The agent must use the database and cannot invent information. Expand prompts/prompt.md so the agent knows to call these tools for price and stock questions and add or update return types to models.py. In output/harness.md list each tools and explain what model fields it uses and why

## Problem 7

1. Problem 7: Now we will add a cool feature to the site, the chat search should be able to update the page, so if a customer asks what hoodies are available the chat should both respond and then update the site to show those matching items as product cards. This is an api contract where the ai agent returns structured product matches and the front end renders them on the website. Make sure single item page on click behaivor that we built in problem 3 still works. update prompts/prompt.md and output/harness.md to show how search results reach the page

## Problem 8

1. Problem 8: Now we will work on customer memory, when a customer logs in save their chat history in an apporiate table and reload it when they return, the agent should know their name and email along with context on previous conversations ( put code into the agent context), guests can still chat but history only persists for logged in users. Document changes in output/harness.md to show how user history is stored, what customer fields the agent sees, and how past context is passed.

## Problem 9

1. Problem 9: Now it is time to iterate, make two usability improvement for the front end and 2 agent / backend improvements. Document your improvements in output/usability.md and for each imrpovement what you added and why it improves the experience or makes the site better. Make sure all improvements show up in the final application

## Problem 10

1. Problem 10: Add creative designs that makes it feel like a real but warm and inviting campus custom store front. I am being graded on imagination, craetivity and design. Write output/design.md to document what you changed and why it helps the store (every change must help the store attract customers and turn those customers into buyers) Keep it short and concise

## Problem 11

1. Problem 11: test the live site and document it in  output/app_check.html (a page you can double click open), include clear screenshots and short captions for the chat checking the inventory level of an item, the dynamic search results cards appearing after a question, and one usability feature you added in problem 9. (let me know if i need to manually take the screenshots but it would be great if you can). Make sure app_check is easy to read and grade, put screenshots in output/app_checks_images/ and link them from app_check.html with relevant paths

## Problem 12

1. Problem 12: Keep and append only output/audit_trail.json of an agent loop activity, do not wipe between runs. ALso think of important guardrails and guidelines to give the ai agent (cost/ token caps, only answering questions on topic for the site, etc) put that in prompts/prompt.md. Finally finish output/harness.md so it is clear how the system works model fields in model.py and why you chose them, tools and abilities, safety rules, and specs (loop limits, result caps, models, how to run front + back)

## Final review

1. Review the AI_prompts.md file and grade the project we put together and do one final QA while you are at it

## Problem 13

1. Problem 13: Upload the project to GitHub so I can submit, i have already set up the github repository at https://github.com/AndrewFryeYale/hw4.git, let me know if there is anything else you need. You should also have context on my github from previous work
