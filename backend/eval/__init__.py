"""Model evaluation harness for the Celerius artifact generators.

This package compares language models (frontier APIs and locally hosted
open-weight models) on the platform's real generation prompts. It exists to
answer a single question empirically: what is the smallest / cheapest model
that produces review-ready CDISC and regulatory artifacts?

It is a developer tool. It does not touch the application's request path,
database, or CIP audit chain — it imports the generator classes only to reuse
their exact system prompts, user-prompt construction, and JSON parsing.
"""
