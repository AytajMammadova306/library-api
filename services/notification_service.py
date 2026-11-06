
def notify(email, subject, body, send=True):
    if not send:
        return

    with open("outbox.txt", "a") as f:
        f.write(
            "TO: " + email
            + " | SUBJECT: " + subject
            + " | BODY: " + body + "\n"
        )
