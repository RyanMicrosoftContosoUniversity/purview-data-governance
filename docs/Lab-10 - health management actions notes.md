# Lab‑10: Health management actions – Speaker notes

## Purpose and goals

- Use **health actions** to respond to data estate health issues identified by controls.  Actions guide remediation and track progress【414200913575546†L19-L33】.
- Understand the **roles** required to create and manage actions and how to interpret the health action dashboard.

## What are health actions?【414200913575546†L19-L33】

- Health actions are **tasks** created in response to a failing or warning control.  They assign responsibility and due dates to improve specific metrics (e.g., “Increase classification coverage for Finance domain to 80%”).
- Each action has:
  - **Status**: Not started, In progress, Completed.
  - **Severity**: Critical, High, Medium, Low – based on the impact of the underlying issue.
  - **Owner(s)**: individuals responsible for completing the action.
  - **Due date** and **notes**.
- Actions are tracked in the Purview portal; they appear on the **Health actions dashboard**.

## Roles and permissions【414200913575546†L19-L33】

- To create or edit health actions you need to be a **Purview Administrator** or be assigned the **Data Estate Health Owner** role.
- Domain leads or collection administrators may also create actions within their scope; RBAC ensures they cannot alter controls outside their domain.

## Using the Health actions dashboard【414200913575546†L48-L67】

- The dashboard lists all actions grouped by **status**, **severity** and **domain**.
- Charts summarise action counts by status and highlight overdue tasks; use filters to focus on a particular domain or pillar.
- You can drill into an action to view details, update status or add comments.

## Creating and managing actions

- When a control (e.g., classification coverage) is in warning or poor status, select the **Create action** option.
- Provide a **title**, **description** and **severity** for the action.  Assign an **owner** and set a **due date**.
- Save the action; it will now appear in the dashboard.  Notification emails may be sent to the owner.
- Owners should **update the status** as they work on remediation; comments can document progress and obstacles.
- Once completed, mark the action as **Completed**; the associated control status will update automatically after the next scan cycle.

## Lab tasks and walkthrough

- In the health controls page (Lab 08), identify a control in warning state (e.g., low term coverage) and click **Create action**.
- Fill out the action form: specify the severity, due date and owner.  Add context explaining why the metric is low.
- View the newly created action in the dashboard; explore filtering and sorting options.
- As the owner, update the action status to **In progress** and add a note describing planned steps.
- Demonstrate how completing the action and improving the underlying metric changes the overall health score.

## Tips for facilitators

- emphasise that health actions are a **collaboration tool**; encourage transparency and timely updates.
- Remind participants to choose realistic due dates and to provide adequate context for actions to avoid confusion.
- Encourage domain leads to review actions regularly to ensure progress.

## References

1. Purpose and creation of health actions【414200913575546†L19-L33】.
2. Health actions dashboard and structure【414200913575546†L48-L67】.
