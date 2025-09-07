# Prompts for application
1. Create a utility that is able to evaluate the contributions of an individual team member during a specified time period. 
2. This will included information from Jira, Confluence and Github. 
3. I'm interested in gauging levels of:
   * involvement
   * significance of contributions
   * effectiveness of contributions
   * complexity
   * time required for contribution
   * number of later bugs and fixes submitted against the contribution
4. I have API access tokens for Jira and Confluence. I also have a GitHub personal access token.
5. Tokens will not have admin-level access.
6. For GitHub, all repos will exist within a single organization.
7. It would be limited to a single Jira project, a single Confluence Space and a single GitHub org
8. Timeframe would be a start/end date, typically monthly or quarterly.  Best to specify date range as args.
9. Ask questions if you need to figure out how to proceed with this?