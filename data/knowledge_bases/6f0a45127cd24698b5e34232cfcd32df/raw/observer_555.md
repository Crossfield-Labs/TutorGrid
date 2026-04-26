# Observer Pattern

Observer pattern defines a one-to-many dependency between objects.

When the subject changes state, all observers are notified and updated automatically.

It is commonly used in event systems, publish-subscribe workflows, GUI listeners, and reactive programming.

Key roles:
- Subject: keeps observer list and sends notifications.
- Observer: receives update notifications.
- ConcreteObserver: performs actual update logic.

A simple example is a newsletter: the newsletter publisher is the subject, and subscribers are observers.
