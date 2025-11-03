.PHONY: help install clean test scrape analyze-clubs

# Python virtual environment
VENV = venv_gvsa_scrape
PYTHON = ${VENV}/bin/python3
PIP = ${VENV}/bin/pip

# Database file
DB = gvsa_data.db

help:
	@echo "Available targets:"
	@echo "  make install        - Create virtual environment and install dependencies"
	@echo "  make scrape         - Run the scraper to fetch all data"
	@echo "  make test           - Test the parser with extracted data"
	@echo "  make analyze-clubs  - Analyze clubs and their performance"
	@echo "  make clean          - Remove virtual environment and database"
	@echo "  make help           - Show this help message"

${VENV}:
	python3 -m venv ${VENV}
	${PIP} install --upgrade pip
	${PIP} install -r requirements.txt

install: ${VENV}

scrape: ${VENV}
	${PYTHON} scraper.py ${DB}

test: ${VENV}
	${PYTHON} -c "from parse_standings import parse_standings; content = open('extracted_responses/standings.jsp').read(); data = parse_standings(content); print(f'Teams: {len(data[\"teams\"])}'); print(f'Matches: {len(data[\"matches\"])}'); print('First team:', data['teams'][0] if data['teams'] else 'None'); print('First match:', data['matches'][0] if data['matches'] else 'None')"

analyze-clubs: ${VENV}
	${PYTHON} analyze_clubs.py ${DB}

clean:
	rm -rf ${VENV}
	rm -f ${DB}
	rm -rf extracted_responses

