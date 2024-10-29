---
title: Scrum-15
---

# User Stories

## Scrum-15

### Title

As a user, I want to see my tasks but not thoses of other users, so that my tasks are only visible by me

### Story points

2

### Epic

Authentication

### Tests

| Process                        | Expected result                                             |
| ------------------------------ | ----------------------------------------------------------- |
| User create an account         | User is redirected to the home page with an empty task list |
| User add a task                | The task is added to the task list                          |
| User log out                   | User is redirected to the login page                        |
| User create another account    | User is redirected to the home page with an empty task list |
| User add a task                | The task is added to the task list                          |
| User log in with first account | User is redirected to the home page with the first task     |

[Previous](/scrum14)

<p align="right">
    [Next](/scrum16)
</p>