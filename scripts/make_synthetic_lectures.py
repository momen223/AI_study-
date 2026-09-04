"""
Generate synthetic lecture PDFs for the genericity / subject-isolation
validation (FINAL_REMAINING_WORK Tasks 3 & 4).

These are original, self-contained lecture-style texts covering three
unrelated subjects (Machine Learning, Computer Networks, Database Systems).
They are used ONLY to exercise the generic, subject-agnostic RAG pipeline:
the same production prompts/agents must answer questions from any of them
without any per-subject modification.

The Data Warehousing corpus already exists in data/ as real lecture PDFs, so
the DW subject is reused as-is for cross-subject isolation checks.

Output: data/Lecture - Machine Learning.pdf, data/Lecture - Computer
Networks.pdf, data/Lecture - Database Systems.pdf
"""

import os

from fpdf import FPDF

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def make_pdf(title, sections):
    """sections: list of (heading, [paragraphs]). Each section starts on a
    new PDF page so character-based chunking produces clean per-topic
    chunks (an important property for the small-corpus genericity test)."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    first = True
    for heading, paragraphs in sections:
        if first:
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.multi_cell(0, 10, title)
            pdf.ln(4)
            first = False
        else:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 8, heading)
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 11)
        for para in paragraphs:
            pdf.multi_cell(0, 6, para)
            pdf.ln(2)

    out = os.path.join(DATA_DIR, f"Lecture - {title}.pdf")
    pdf.output(out)
    return out


ML_SECTIONS = [
    ("1. What is Machine Learning", [
        "Machine learning is the study of computer programs that improve their "
        "performance on a task through experience, without being explicitly "
        "programmed for every possible input. A learning algorithm takes a set "
        "of examples and produces a model that can make predictions on new, "
        "unseen data.",
        "The central idea is that the program learns a function from input "
        "features to an output value. The quality of the learned function "
        "depends on the amount and quality of the training data, the choice "
        "of the model family, and how the training procedure is configured.",
        "A model is a concrete learned object, such as a decision tree or a "
        "set of weights, that the algorithm produces after training. The "
        "algorithm is the procedure used to find that model from the data. "
        "The data is organized as rows, where each row is one example, and "
        "columns, where each column is one attribute or feature of the "
        "example.",
        "Machine learning systems appear throughout everyday technology. "
        "Search engines rank results, email services filter spam, streaming "
        "services recommend shows, and virtual assistants transcribe speech. "
        "What unifies these examples is that the behaviour is learned from "
        "data rather than written by hand. This makes machine learning "
        "especially useful for problems where it is hard to write an exact "
        "set of rules by hand, such as recognising objects in images or "
        "understanding free-form language.",
    ]),
    ("2. Supervised and Unsupervised Learning", [
        "In supervised learning, every training example comes with a label. "
        "The algorithm learns to map features to those known labels. "
        "Classification is the supervised task where the output is one of a "
        "finite set of categories, such as deciding whether an email is spam "
        "or not spam.",
        "Regression is the supervised task where the output is a continuous "
        "number, such as predicting the price of a house from its size and "
        "location. In both cases the labels are known during training, which "
        "is why the learning is described as supervised: a teacher provides "
        "the correct answers that the algorithm is trying to reproduce.",
        "In unsupervised learning, the training data has no labels. The "
        "algorithm must find structure on its own. Clustering groups similar "
        "examples together, such as grouping customers by purchasing "
        "behaviour. Dimensionality reduction compresses the data into fewer "
        "dimensions while trying to preserve the important relationships "
        "between examples.",
        "A third family is reinforcement learning, where an agent learns by "
        "taking actions in an environment and receiving rewards or penalties "
        "for the outcomes of those actions. The agent's goal is to choose a "
        "policy that maximises the total reward it receives over time, rather "
        "than trying to reproduce fixed labels from a dataset.",
    ]),
    ("3. Training, Testing and Generalization", [
        "A dataset is usually split into a training set and a test set. The "
        "training set is used to fit the model, and the test set is used to "
        "estimate how well the model performs on data it has never seen. "
        "This measures generalization, which is the ability of the model to "
        "make useful predictions on new examples it did not encounter during "
        "training.",
        "A model that memorizes the training data but fails on new data is "
        "said to overfit. Overfitting happens when the model is too complex "
        "relative to the amount of training data, so it learns noise rather "
        "than the underlying pattern. A complex model has enough capacity to "
        "match every detail of the training set, including random fluctuations "
        "that do not generalise.",
        "Underfitting is the opposite problem, when the model is too simple "
        "to capture the pattern at all. A very flexible model that is allowed "
        "to become arbitrarily complex can fit the training data perfectly but "
        "loses its ability to generalise, while a very rigid model may never "
        "capture the pattern even in the training data.",
        "The goal is to balance model complexity so the model generalizes "
        "well to unseen examples. Techniques such as cross-validation and "
        "regularisation help find this balance. Cross-validation repeats the "
        "training and evaluation process on several different splits of the "
        "data, and regularisation adds a penalty for excessive complexity so "
        "that the model prefers simpler explanations when the data does not "
        "justify more detail.",
    ]),
    ("4. Features and Evaluation", [
        "Features are the individual measurable properties used as input to "
        "the model. Feature engineering is the process of selecting and "
        "transforming features so that they are informative for the task.",
        "Good features capture the structure that the model needs to make "
        "predictions. Sometimes raw data is not directly usable, so it must "
        "be cleaned, normalised, or combined into derived features. Removing "
        "irrelevant features can also reduce overfitting by simplifying the "
        "model.",
        "Accuracy is the fraction of test examples that the model labels "
        "correctly. Precision measures how many of the positively predicted "
        "examples are actually correct. Recall measures how many of the true "
        "positive examples the model managed to find.",
        "There is a trade-off between precision and recall. Raising the bar "
        "for what counts as a positive prediction tends to increase precision "
        "but decrease recall, and lowering it does the opposite. For an email "
        "spam filter a false positive could mean deleting an important "
        "message, so precision matters most, whereas for cancer screening a "
        "missed case is far worse, so recall matters most.",
    ]),
]


NET_SECTIONS = [
    ("1. Introduction to Computer Networks", [
        "A computer network connects multiple computers so they can exchange "
        "data and share resources. Networks are built from hosts, switches, "
        "and routers connected by links such as copper cable, fiber optics, "
        "or wireless radio.",
        "The primary purpose of a network is reliable communication. Data is "
        "broken into small units called packets, which travel independently "
        "through the network and are reassembled at the destination. "
        "Packets carry the data itself together with headers that hold "
        "addressing and control information.",
        "Networks can be described by their size and scope. A local area "
        "network, or LAN, spans a single building or campus and is usually "
        "owned by one organisation. A wide area network, or WAN, spans "
        "larger geographic distances and often connects several LANs "
        "together using leased lines or the public Internet.",
        "Addressing is fundamental to communication. Every device on a "
        "network needs an address so that packets can be delivered to the "
        "correct destination. On the modern Internet this addressing is "
        "provided by the Internet Protocol, or IP, which assigns each "
        "interface a unique IP address.",
    ]),
    ("2. The OSI and TCP/IP Models", [
        "The OSI reference model divides network communication into seven "
        "layers: physical, data link, network, transport, session, "
        "presentation, and application. Each layer provides services to the "
        "layer above it and hides the details of the layers below.",
        "The physical layer deals with transmitting raw bits over a link. "
        "The data link layer moves frames between directly connected nodes "
        "and handles error detection. The network layer routes packets "
        "between hosts across multiple links, and the transport layer "
        "provides end-to-end delivery of data between applications.",
        "The TCP/IP model is the practical model used on the Internet. It has "
        "four layers: link, internet, transport, and application. The "
        "internet layer handles addressing and routing, and the transport "
        "layer handles end-to-end delivery of data between applications.",
        "Layering is a design principle that keeps each layer relatively "
        "simple and interchangeable. Because each layer exposes a well "
        "defined interface to the layer above, a change in one layer, such "
        "as replacing the physical medium, does not force a change in the "
        "other layers, which is why so many very different link "
        "technologies can all carry the same Internet traffic.",
    ]),
    ("3. Routing and Latency", [
        "Routing is the process of choosing the path that packets take from "
        "source to destination. Routers exchange information about the "
        "network topology and use this to forward each packet toward its "
        "destination.",
        "Each router keeps a forwarding table that maps destination "
        "addresses to the next hop on the path. When a packet arrives, the "
        "router looks up the destination in its table and forwards the "
        "packet to the next router. This process repeats at every router "
        "until the packet reaches its final destination.",
        "The path a packet takes is typically not the shortest by distance "
        "but the path with the lowest overall cost, where cost can reflect "
        "bandwidth, delay, reliability, or administrative policy. Routing "
        "protocols allow routers to learn the topology and to adapt when "
        "links fail or new links become available.",
        "Latency is the time it takes for a message to travel from sender to "
        "receiver. It includes transmission delay, propagation delay, and "
        "queueing delay at routers. Low latency is important for interactive "
        "applications such as video calls and online gaming.",
        "Propagation delay is the time for a signal to cross a physical "
        "link, which grows with the distance the link covers. Transmission "
        "delay is the time to push a packet of a given size onto the link, "
        "which grows with packet size and shrinks as bandwidth grows. "
        "Queueing delay is the time a packet spends waiting in a router "
        "buffer, which grows as the network becomes congested.",
        "Throughput is the amount of data that can be moved per unit of time, "
        "usually measured in bits per second. A link with high bandwidth has "
        "the capacity for high throughput, but real throughput is also "
        "limited by latency and congestion because the sender cannot push "
        "more data into the network than the slowest link and the queues "
        "along the path will accept.",
    ]),
    ("4. Reliable Transport", [
        "The Transmission Control Protocol, or TCP, provides reliable, "
        "ordered delivery of a stream of bytes between two applications. It "
        "detects lost packets and retransmits them, and it controls the rate "
        "of sending to avoid overwhelming the network.",
        "TCP establishes a connection before exchanging data. Each byte "
        "stream is broken into segments, and each segment carries a sequence "
        "number so that the receiver can detect losses and put out-of-order "
        "data back in the correct order. When the receiver acknowledges "
        "received data, the sender can infer which segments were lost.",
        "Because the network can lose or reorder packets, TCP must cope with "
        "uncertainty. A timeout or a set of duplicate acknowledgements tells "
        "the sender that a segment was lost, and the sender retransmits it. "
        "This end-to-end reliability is what makes TCP the default choice "
        "for web browsing, email, and file transfers.",
        "TCP also performs congestion control. It slowly increases its "
        "sending rate until a loss is detected, then backs off, so that many "
        "TCP flows sharing a link can split the available bandwidth fairly "
        "without overloading the network.",
        "The User Datagram Protocol, or UDP, provides a lightweight, "
        "connectionless service. UDP adds no guarantees of delivery or "
        "ordering, but it has low overhead and low latency, making it useful "
        "for real-time applications such as voice and video where a delayed "
        "or retransmitted packet is not worth waiting for.",
        "Because UDP does not establish a connection and does not track each "
        "segment, its header is much smaller than TCP's header and the "
        "protocol imposes no retransmission delay. This makes UDP attractive "
        "for DNS lookups, live streaming, online gaming, and voice over IP, "
        "where latest data matters more than reliable delivery of older "
        "data.",
    ]),
]


DB_SECTIONS = [
    ("1. The Relational Model", [
        "A relational database organizes data into tables. Each table, also "
        "called a relation, is made up of rows and columns. A row represents "
        "a single record, and a column represents an attribute of that "
        "record.",
        "The relational model was proposed by E. F. Codd in 1970 as a way to "
        "separate the logical structure of data from the way it happens to "
        "be stored on disk. Users work with tables and the operations of "
        "relational algebra rather than with physical storage details.",
        "A primary key is a column or set of columns whose values uniquely "
        "identify each row in a table. A foreign key is a column that refers "
        "to the primary key of another table and is used to create a "
        "relationship between the two tables.",
        "Because a primary key must be unique and non-null, it guarantees "
        "that every row in a table can be identified unambiguously. The "
        "foreign key is the mechanism that implements relationships: a row "
        "in one table can point to a row in another table through the value "
        "of the foreign key column.",
    ]),
    ("2. SQL and Queries", [
        "Structured Query Language, or SQL, is the standard language for "
        "interacting with relational databases. A SELECT statement retrieves "
        "data from one or more tables and can filter rows with a WHERE "
        "clause.",
        "A basic query names the columns to return, the table to read from, "
        "and any conditions the rows must satisfy. The database system "
        "optimises the query, plans an execution strategy, and returns the "
        "matching rows. The same declarative query returns the same logical "
        "result regardless of how the database physically executes it.",
        "Joins combine rows from two tables based on a related column, such "
        "as a foreign key. An INNER JOIN returns only rows that match in "
        "both tables, while a LEFT JOIN also returns all rows from the left "
        "table, even those with no match on the right.",
        "Joining is one of the most powerful and most used operations in "
        "relational databases because it lets information stored in "
        "different tables be combined into a single result. Deciding which "
        "join type to use depends on which rows should be kept when there is "
        "no matching row on the other side.",
    ]),
    ("3. Normalization and Design", [
        "Normalization is the process of organizing the columns and tables of "
        "a database to reduce redundant data and improve data integrity. The "
        "goal is to eliminate duplicate information so that each fact is "
        "stored in exactly one place.",
        "Redundant data is a problem because it wastes space and, more "
        "importantly, because it creates the risk of inconsistency: the same "
        "fact copied in several places can be updated in one place but not "
        "the others. Normalization reduces this risk by structuring the "
        "tables so each fact appears once.",
        "A design is said to be in first normal form when every column holds "
        "atomic, indivisible values and there are no repeating groups. "
        "Removing partial and transitive dependencies moves a design toward "
        "higher normal forms.",
        "Second normal form removes partial dependencies, where a column "
        "depends on only part of a composite key. Third normal form removes "
        "transitive dependencies, where a column depends on another "
        "non-key column rather than directly on the key. Each step reduces "
        "the ways in which redundant data can be introduced.",
    ]),
    ("4. Transactions and ACID", [
        "The four ACID properties are atomicity, consistency, isolation, and "
        "durability. Together they guarantee that a database remains correct "
        "in the face of failures and concurrency. Atomicity keeps each "
        "transaction all-or-nothing, consistency keeps the data valid, "
        "isolation keeps concurrent transactions separate, and durability "
        "keeps committed changes permanent.",
        "A transaction is a sequence of database operations that must be "
        "executed as a single unit. Either all of the operations complete, or "
        "none of them take effect. Transactions are committed to make their "
        "changes permanent, or rolled back to undo them.",
        "Transactions protect the database from failures and from concurrent "
        "conflicts. If a failure occurs partway through a transaction, the "
        "database restores the state to what it was before the transaction "
        "began, so a partially applied change never becomes visible.",
        "The ACID properties describe what makes a transaction reliable. "
        "Atomicity means the transaction is all-or-nothing. Consistency means "
        "the database moves from one valid state to another. Isolation means "
        "concurrent transactions do not interfere with each other. Durability "
        "means committed changes survive a system failure.",
        "Atomicity is achieved by logging the operations of the transaction "
        "so they can be undone if the transaction never completes. "
        "Durability is achieved by writing committed changes to stable "
        "storage before acknowledging success, so the change is not lost "
        "even if the machine loses power afterward. Consistency is enforced "
        "by the database and the application together: the database checks "
        "constraints such as uniqueness and foreign-key integrity so that no "
        "commit can leave the data in an invalid state.",
        "Isolation is the property that stops two transactions running at the "
        "same time from observing each other's partial work. Without "
        "isolation, one transaction could read a value that another "
        "transaction later rolls back, producing a result that could not "
        "occur if the transactions had run one after the other. Strong "
        "isolation guarantees serializable behaviour, while weaker isolation "
        "levels permit more concurrency in exchange for accepting some "
        "anomalies.",
    ]),
]


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    created = []
    created.append(make_pdf("Machine Learning", ML_SECTIONS))
    created.append(make_pdf("Computer Networks", NET_SECTIONS))
    created.append(make_pdf("Database Systems", DB_SECTIONS))
    for path in created:
        print("created:", path, os.path.getsize(path), "bytes")


if __name__ == "__main__":
    main()
