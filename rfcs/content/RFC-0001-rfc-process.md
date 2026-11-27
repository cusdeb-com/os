# RFC Process

This RFC introduces a Request for Comments (RFC) process for CusDeb OS, allowing members of the CusDeb OS community and the wider free and open source software community to participate in discussions on decisions that significantly impact the project.

## Motivation

The adoption of an RFC-based approach to the development of CusDeb OS was inspired by the project-wide RFC process adopted by GNOME on October 30, 2026, but is not a copy of it. Our primary motivation for adapting such a process to CusDeb OS is to ensure that we, the people behind CusDeb OS, understand the technical decisions we make within the project. In the age of generative AI, virtually anyone can propose a solution of any level of complexity without understanding its intricacies. However, such solutions may not necessarily fit into the existing architecture of the project or take its long-term maintainability into account. CusDeb RFCs are therefore intended to help us determine whether we understand the proposed changes well enough to take responsibility for them. To this end, they were conceived as something halfway between GNOME RFCs, whose primary purpose is to bring ideas to the table and reach consensus through discussion without necessarily going into implementation details, and IETF RFCs, which are used, among other things, to specify Internet standards.

It is perfectly reasonable to wonder how CusDeb RFCs differ from specifications in spec-driven development (SDD). In terms of their technical content, there is no fundamental difference. There is nothing wrong with thinking of them as such, but the primary purpose of CusDeb RFCs is to demonstrate to everyone involved in the development of CusDeb OS, as well as to other members of the community who care about the project, that the person proposing a technical solution fully understands it and is willing to take responsibility for it.

## Definitions

### Core Team

The Core Team is the group responsible for the technical direction, architecture, and development of CusDeb OS, as defined in [GOVERNANCE.md](/GOVERNANCE.md).

### Project Lead

The Project Lead is a member of the Core Team with final decision-making authority in cases of unresolved disagreements, as defined in [GOVERNANCE.md](/GOVERNANCE.md).

## Proposal

### When to Create an RFC

RFCs are intended for significant changes to the architecture, technical direction, or user experience of CusDeb OS. Examples include:
- Major architectural changes.
- Changes to core components or underlying technologies.
- Significant user interface or user experience changes.
- Changes affecting multiple components.
- Resolving technical disagreements.
- Amending or superseding existing RFCs.

Routine changes, bug fixes, and minor improvements do not require an RFC.

### Proposing an RFC

Any Core Team member may propose an RFC by submitting a Pull Request (PR) to the main CusDeb OS repository. The RFC is a Markdown document placed in the `rfcs/content/` directory, following the `RFC-XXXX-<title>.md` naming convention, where the title is written in kebab-case.

RFCs should follow the repository's RFC template. The author may update the proposed RFC throughout the review process.

### Referencing RFCs

When referring to CusDeb OS RFCs, especially outside the project's GitHub repositories, the CD/RFC XXXX notation is __recommended__, where XXXX is the four-digit RFC number. This notation helps distinguish CusDeb OS RFCs from IETF RFCs and those of other projects.

### Review

All discussions take place in the corresponding GitHub PR. Anyone may participate in the discussion, suggest changes, propose alternatives, or raise concerns. The RFC author is expected to address concerns by refining the proposal or providing technical explanations. The Core Team evaluates the proposal and works toward consensus.

### Final Comment Period

Once the discussion has slowed down, the RFC author may announce a Final Comment Period (FCP), specifying the proposed outcome: acceptance or rejection. The FCP lasts 48 hours. If significant new concerns arise or substantial changes are made to the proposal, the FCP may be canceled and restarted.

### Decision

After the FCP, the Core Team decides whether to accept or reject the RFC. Decisions should be reached through consensus whenever possible. In cases of unresolved disagreements, the Project Lead has final decision-making authority.

An accepted RFC is merged into the repository. A rejected RFC is closed without merging.

### Amending Accepted RFCs

Accepted RFCs may be amended or superseded through new RFCs. Minor editorial corrections that do not change the meaning of an accepted RFC may be submitted directly as PRs.
