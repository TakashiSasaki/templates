---
name: standardized-response-writer
description: Produce a standardized response by filling a maintained text asset while preserving its required section order.
---

# Standardized response writer

## Purpose

Create a consistent response from supplied facts using the maintained response template.

## Use this skill when

Use this skill when the requested output must follow the repository's standard response structure.

## Assets

Asset: assets/response-template.txt
Use when: preparing the final standardized response
Handling: copy the headings, replace each bracketed field with supported facts, and remove unused optional lines
Must remain unchanged: heading order and the final verification heading

## Workflow

1. Read the supplied facts and identify unsupported or missing details.
2. Open `assets/response-template.txt`.
3. Fill each applicable field without changing the required heading order.
4. Remove unused optional lines and verify the completed response.

## Output requirements

Return the completed response with no unfilled bracketed fields.

## Validation

Confirm that the heading order matches the asset and every inserted fact is supported by the supplied input.

## Safety and approval

Do not fabricate missing values or include confidential information not authorized for the response.

Selected profiles: asset-driven
