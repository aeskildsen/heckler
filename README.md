# heckler

Infrastructure for LLM-generated commentary on live coding

## Layout diagram

┌─────────────────────┬──────────┐
│                     │   LLM    │
│   SuperCollider     │ responses│
│      Code           │  +memes  │
│      Editor         ├──────────┤
│     (2/3 width)     │   Post   │
│                     │  Window  │
│                     ├──────────┤
│                     │  Scope   │
└─────────────────────┴──────────┘