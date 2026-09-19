import io
import re
import logging
from typing import Dict, List, Tuple, Any

logger = logging.getLogger(__name__)

TRACK_TAXONOMY = {
    "full_stack": {
        "title": "Full Stack Software Engineering",
        "description": "Modern web platforms, distributed microservices, RESTful APIs, and responsive frontend architectures.",
        "skills": [
            {"name": "Python", "patterns": [r"\bpython\b", r"\bdjango\b", r"\bflask\b", r"\bfastapi\b"]},
            {"name": "JavaScript", "patterns": [r"\bjavascript\b", r"\bjs\b", r"\bes6\b"]},
            {"name": "TypeScript", "patterns": [r"\btypescript\b", r"\bts\b"]},
            {"name": "React", "patterns": [r"\breact\b", r"\breactjs\b", r"\bnext\.?js\b", r"\bvite\b"]},
            {"name": "Node.js", "patterns": [r"\bnode(?:\.js)?\b", r"\bexpress(?:\.js)?\b", r"\bnest(?:\.js)?\b"]},
            {"name": "HTML & CSS", "patterns": [r"\bhtml5?\b", r"\bcss3?\b", r"\btailwind\b", r"\bbootstrap\b", r"\bsass\b"]},
            {"name": "SQL & Relational DB", "patterns": [r"\bsql\b", r"\bpostgresql\b", r"\bmysql\b", r"\bsqlite\b", r"\bprisma\b"]},
            {"name": "NoSQL / MongoDB", "patterns": [r"\bmongodb\b", r"\bnosql\b", r"\bcassandra\b"]},
            {"name": "Redis Caching", "patterns": [r"\bredis\b", r"\bcaching\b", r"\bmemcached\b"]},
            {"name": "Git & Version Control", "patterns": [r"\bgit\b", r"\bgithub\b", r"\bgitlab\b"]},
            {"name": "REST APIs", "patterns": [r"\brest(?:ful)?\b", r"\bapi[s]?\b", r"\bgraphql\b", r"\bpostman\b", r"\bgrpc\b"]},
            {"name": "WebSockets & Real-time", "patterns": [r"\bwebsocket[s]?\b", r"\bsocket\.io\b", r"\bevent-driven\b", r"\bwebrtc\b"]},
            {"name": "Microservices & Architecture", "patterns": [r"\bmicroservices?\b", r"\bsystem design\b", r"\bscalab(?:le|ility)\b", r"\bload balanc(?:er|ing)\b"]},
            {"name": "Data Structures & Algorithms", "patterns": [r"\bdata structures\b", r"\balgorithms\b", r"\bdsa\b", r"\bleetcode\b"]},
            {"name": "Docker & Containers", "patterns": [r"\bdocker\b", r"\bcontainers?\b", r"\bdocker-compose\b", r"\bk8s\b", r"\bkubernetes\b"]},
            {"name": "Cloud Deployment", "patterns": [r"\bci/cd\b", r"\baws\b", r"\bazure\b", r"\bgcp\b", r"\bgithub actions\b", r"\bvercel\b"]},
            {"name": "Testing & QA", "patterns": [r"\bjest\b", r"\bpytest\b", r"\bplaywright\b", r"\bcypress\b", r"\bunit test(?:ing)?\b"]}
        ]
    },
    "data_science_ml": {
        "title": "Data Science & AI / ML",
        "description": "Predictive modeling, deep learning architectures, feature engineering, NLP, and enterprise analytics.",
        "skills": [
            {"name": "Python for Data Science", "patterns": [r"\bpython\b", r"\bjupyter\b"]},
            {"name": "Pandas & NumPy", "patterns": [r"\bpandas\b", r"\bnumpy\b"]},
            {"name": "Scikit-Learn & ML Algorithms", "patterns": [r"\bscikit-learn\b", r"\bsklearn\b", r"\brandom forest\b", r"\bxgboost\b", r"\bregression\b", r"\bclassification\b"]},
            {"name": "Deep Learning (PyTorch / TensorFlow)", "patterns": [r"\bdeep learning\b", r"\bpytorch\b", r"\btensorflow\b", r"\bkeras\b", r"\bcnn\b", r"\brnn\b", r"\blstm\b"]},
            {"name": "Transformers & Hugging Face", "patterns": [r"\btransformers\b", r"\bhugging\s?face\b", r"\bbert\b", r"\bgpt\b", r"\bllm\b"]},
            {"name": "Natural Language Processing (NLP)", "patterns": [r"\bnlp\b", r"\bnatural language processing\b", r"\bnltk\b", r"\bspacy\b", r"\btokeniz(?:ation|er)\b"]},
            {"name": "Computer Vision & OpenCV", "patterns": [r"\bcomputer vision\b", r"\bopencv\b", r"\byolo\b", r"\bimage processing\b"]},
            {"name": "Feature Engineering & Preprocessing", "patterns": [r"\bfeature engineering\b", r"\bpreprocessing\b", r"\bdata cleaning\b", r"\bshap\b", r"\boptuna\b"]},
            {"name": "SQL & Data Extraction", "patterns": [r"\bsql\b", r"\bdatabase\b", r"\bquery\b", r"\bwindow functions\b"]},
            {"name": "Data Visualization (Tableau / Plotly)", "patterns": [r"\bmatplotlib\b", r"\bseaborn\b", r"\bplotly\b", r"\btableau\b", r"\bpower\s?bi\b"]},
            {"name": "Statistical Analysis & Hypothesis Testing", "patterns": [r"\bstatistics\b", r"\bhypothesis testing\b", r"\bp-value\b", r"\ba/b test(?:ing)?\b"]},
            {"name": "MLOps & Model Deployment", "patterns": [r"\bmlops\b", r"\bmlflow\b", r"\bfastapi\b", r"\bdocker\b", r"\bmodel monitoring\b"]}
        ]
    },
    "gen_ai_engineer": {
        "title": "Generative AI & LLM Systems",
        "description": "Large Language Models, Retrieval-Augmented Generation (RAG), agentic workflows, and vector embeddings.",
        "skills": [
            {"name": "Large Language Models (LLMs)", "patterns": [r"\bllm[s]?\b", r"\blarge language models?\b", r"\bgpt-?4\b", r"\bclaude\b", r"\bllama\b", r"\bgemini\b"]},
            {"name": "LangChain & LlamaIndex", "patterns": [r"\blangchain\b", r"\bllamaindex\b", r"\blanggraph\b", r"\bhaystack\b"]},
            {"name": "RAG (Retrieval-Augmented Generation)", "patterns": [r"\brag\b", r"\bretrieval[- ]augmented\b", r"\bchunking\b", r"\bhybrid search\b"]},
            {"name": "Vector Databases (Pinecone / Chroma / FAISS)", "patterns": [r"\bpinecone\b", r"\bchromadb\b", r"\bchroma\b", r"\bfaiss\b", r"\bweaviate\b", r"\bqdrant\b", r"\bvector (?:db|database|embeddings)\b"]},
            {"name": "Embeddings & Semantic Search", "patterns": [r"\bembeddings?\b", r"\bsemantic search\b", r"\bcosine similarity\b", r"\brerank(?:ing)?\b"]},
            {"name": "Prompt Engineering & Evaluation", "patterns": [r"\bprompt engineering\b", r"\bfew-shot\b", r"\bchain[- ]of[- ]thought\b", r"\bragas\b", r"\btruelens\b"]},
            {"name": "Fine-Tuning (LoRA / QLoRA / PEFT)", "patterns": [r"\bfine[- ]tuning\b", r"\blora\b", r"\bqlora\b", r"\bpeft\b", r"\brlhf\b"]},
            {"name": "AI Agents & Autonomous Workflows", "patterns": [r"\bagents?\b", r"\bautonomous agents\b", r"\btool calling\b", r"\bfunction calling\b", r"\bcrewai\b"]},
            {"name": "Inference Optimization (vLLM / TensorRT)", "patterns": [r"\bvllm\b", r"\btensorrt\b", r"\bquantization\b", r"\bgguf\b", r"\bollama\b"]},
            {"name": "Full-Stack AI Deployment", "patterns": [r"\bfastapi\b", r"\bstreamlit\b", r"\bgradio\b", r"\bdocker\b", r"\bcloud run\b"]}
        ]
    },
    "cloud_devops": {
        "title": "Cloud Computing & DevOps",
        "description": "Infrastructure as Code, CI/CD pipelines, container orchestration, monitoring, and reliability engineering.",
        "skills": [
            {"name": "Linux & Shell Scripting", "patterns": [r"\blinux\b", r"\bbash\b", r"\bshell script(?:ing)?\b", r"\bubuntu\b"]},
            {"name": "Docker & Containerization", "patterns": [r"\bdocker\b", r"\bcontainer(?:s)?\b", r"\bdocker-compose\b"]},
            {"name": "Kubernetes Orchestration", "patterns": [r"\bkubernetes\b", r"\bk8s\b", r"\bhelm\b", r"\bkustomize\b"]},
            {"name": "AWS / Cloud Infrastructure", "patterns": [r"\baws\b", r"\bec2\b", r"\bs3\b", r"\blambda\b", r"\bcloud\b", r"\bazure\b", r"\bgcp\b"]},
            {"name": "CI/CD & GitOps Automation", "patterns": [r"\bci/cd\b", r"\bjenkins\b", r"\bgithub actions\b", r"\bgitlab ci\b", r"\bargocd\b"]},
            {"name": "Terraform & Infrastructure as Code", "patterns": [r"\bterraform\b", r"\bansible\b", r"\biac\b", r"\binfrastructure as code\b"]},
            {"name": "Monitoring & Observability", "patterns": [r"\bprometheus\b", r"\bgrafana\b", r"\belk\b", r"\bdatadog\b", r"\bopentelemetry\b"]},
            {"name": "Networking & Security (VPC / IAM / TLS)", "patterns": [r"\btcp/ip\b", r"\bdns\b", r"\bnginx\b", r"\bvpc\b", r"\biam\b", r"\bssl/tls\b"]},
            {"name": "Python / Go Scripting", "patterns": [r"\bpython\b", r"\bgolang\b", r"\bgo\b"]}
        ]
    },
    "core_cs": {
        "title": "Core Systems & Software Engineering",
        "description": "Low-level systems programming, operating system internals, computer architecture, and algorithms.",
        "skills": [
            {"name": "C / C++ Systems Programming", "patterns": [r"\bc\+\+\b", r"\bcpp\b", r"\bc programming\b", r"\bpointers\b", r"\bc\+\+20\b"]},
            {"name": "Data Structures & Algorithms", "patterns": [r"\bdsa\b", r"\bdata structures\b", r"\balgorithms\b", r"\btree[s]?\b", r"\bgraph[s]?\b"]},
            {"name": "Operating Systems & Concurrency", "patterns": [r"\boperating systems?\b", r"\bthreads?\b", r"\bconcurrency\b", r"\bmemory management\b", r"\bmutex\b", r"\bposix\b"]},
            {"name": "Computer Networks & Sockets", "patterns": [r"\bcomputer networks?\b", r"\bsocket programming\b", r"\btcp\b", r"\budp\b", r"\bosi model\b"]},
            {"name": "Database Internals & SQL", "patterns": [r"\bdbms\b", r"\bsql\b", r"\bacid\b", r"\bindexing\b", r"\btransactions\b", r"\bbtree\b"]},
            {"name": "Object-Oriented Design & Patterns", "patterns": [r"\boop\b", r"\bpolymorphism\b", r"\binheritance\b", r"\bdesign patterns\b", r"\bsolid principles?\b", r"\bjava\b"]},
            {"name": "System Design & Scalability", "patterns": [r"\bsystem design\b", r"\bscalability\b", r"\bcaching\b", r"\bsharding\b", r"\bcap theorem\b"]}
        ]
    },
    "cybersecurity": {
        "title": "Cybersecurity & Information Security",
        "description": "Network security, ethical hacking, cryptography, vulnerability assessment, and SOC defense.",
        "skills": [
            {"name": "Network Security & Protocols", "patterns": [r"\bnetwork security\b", r"\bfirewall\b", r"\bwireshark\b", r"\bvpn\b", r"\bids/ips\b"]},
            {"name": "Cryptography & PKI", "patterns": [r"\bcryptography\b", r"\bencryption\b", r"\brsa\b", r"\baes\b", r"\bssl/tls\b", r"\bhashing\b", r"\bpki\b"]},
            {"name": "Vulnerability Assessment & Pen Testing", "patterns": [r"\bpenetration testing\b", r"\bvulnerability\b", r"\bowasp\b", r"\bburp suite\b", r"\bnmap\b", r"\bmetasploit\b"]},
            {"name": "Web Application Security", "patterns": [r"\bxss\b", r"\bsql injection\b", r"\bcsrf\b", r"\bweb security\b", r"\bssrf\b"]},
            {"name": "Linux & Defensive Command Line", "patterns": [r"\blinux\b", r"\bkali\b", r"\bbash\b", r"\bshell\b"]},
            {"name": "Python for Security & Automation", "patterns": [r"\bpython\b", r"\bscripting\b", r"\bscapy\b"]},
            {"name": "Security Operations (SOC / SIEM)", "patterns": [r"\bsiem\b", r"\bsplunk\b", r"\bsoc\b", r"\blog analysis\b", r"\bincident response\b"]}
        ]
    },
    "mobile_dev": {
        "title": "Mobile App Engineering",
        "description": "Cross-platform and native mobile applications, state management, and mobile API integration.",
        "skills": [
            {"name": "Flutter & Dart", "patterns": [r"\bflutter\b", r"\bdart\b"]},
            {"name": "React Native", "patterns": [r"\breact native\b", r"\bjavascript\b", r"\btypescript\b"]},
            {"name": "Android & Kotlin / Java", "patterns": [r"\bandroid\b", r"\bkotlin\b", r"\bjava\b", r"\bandroid studio\b", r"\bjetpack compose\b"]},
            {"name": "Mobile REST APIs & Networking", "patterns": [r"\brest\b", r"\bapi\b", r"\bjson\b", r"\bhttp\b", r"\bretrofit\b", r"\bdio\b"]},
            {"name": "State Management (Redux / Bloc / Provider)", "patterns": [r"\bredux\b", r"\bbloc\b", r"\bprovider\b", r"\bmobx\b", r"\bzustand\b"]},
            {"name": "Firebase & Push Notifications", "patterns": [r"\bfirebase\b", r"\bfcm\b", r"\bpush notification[s]?\b", r"\bauthentication\b"]},
            {"name": "Mobile CI/CD & Store Deployment", "patterns": [r"\bgit\b", r"\bgoogle play\b", r"\bapp store\b", r"\bapk\b", r"\bfastlane\b"]}
        ]
    },
    "data_eng": {
        "title": "Data Engineering & Big Data Platforms",
        "description": "Scalable ETL pipelines, data warehousing, stream processing, and distributed lakehouse architectures.",
        "skills": [
            {"name": "SQL & Advanced Window Functions", "patterns": [r"\bsql\b", r"\bpostgresql\b", r"\bwindow functions\b", r"\bindexing\b", r"\bcte\b"]},
            {"name": "Python for Data Engineering", "patterns": [r"\bpython\b", r"\bpandas\b", r"\bnumpy\b"]},
            {"name": "Apache Spark / PySpark", "patterns": [r"\bspark\b", r"\bpyspark\b", r"\bdatabricks\b", r"\brdd\b"]},
            {"name": "Data Warehousing (Snowflake / BigQuery)", "patterns": [r"\bdata warehouse\b", r"\bbigquery\b", r"\bsnowflake\b", r"\bredshift\b"]},
            {"name": "Orchestration (Airflow / Prefect)", "patterns": [r"\bairflow\b", r"\bprefect\b", r"\bdag\b", r"\borchestration\b"]},
            {"name": "Kafka & Stream Processing", "patterns": [r"\bkafka\b", r"\bstreaming\b", r"\brabbitmq\b", r"\bevent-driven\b", r"\bflink\b"]},
            {"name": "Data Modeling & dbt (Data Build Tool)", "patterns": [r"\bdbt\b", r"\bdata modeling\b", r"\bstar schema\b", r"\bdata vault\b"]},
            {"name": "Cloud Storage & Lakehouses", "patterns": [r"\bdocker\b", r"\bs3\b", r"\bgcs\b", r"\bdelta lake\b", r"\biceberg\b"]}
        ]
    },
    "qa_automation": {
        "title": "Software Testing & QA Automation",
        "description": "Automated end-to-end testing frameworks, API verification, performance benchmarking, and continuous quality gates.",
        "skills": [
            {"name": "Selenium & Web Automation", "patterns": [r"\bselenium\b", r"\bwebdriver\b"]},
            {"name": "Cypress & Playwright", "patterns": [r"\bcypress\b", r"\bplaywright\b"]},
            {"name": "API Testing (Postman / REST Assured)", "patterns": [r"\bpostman\b", r"\brest assured\b", r"\bapi test(?:ing)?\b"]},
            {"name": "BDD Frameworks (Cucumber / Gherkin)", "patterns": [r"\bcucumber\b", r"\bgherkin\b", r"\bbdd\b"]},
            {"name": "Unit Testing (JUnit / PyTest / TestNG)", "patterns": [r"\bpytest\b", r"\bjunit\b", r"\btestng\b", r"\bunit test(?:ing)?\b"]},
            {"name": "Performance Testing (JMeter / k6)", "patterns": [r"\bjmeter\b", r"\bk6\b", r"\bload test(?:ing)?\b", r"\bperformance test(?:ing)?\b"]},
            {"name": "CI/CD Quality Gates", "patterns": [r"\bci/cd\b", r"\bjenkins\b", r"\bgithub actions\b", r"\bsonarqube\b"]}
        ]
    },
    "blockchain_web3": {
        "title": "Blockchain & Web3 Engineering",
        "description": "Smart contracts, decentralized finance protocols, cryptographic proofs, and Web3 frontend integration.",
        "skills": [
            {"name": "Solidity & Smart Contracts", "patterns": [r"\bsolidity\b", r"\bsmart contracts?\b", r"\berc-?20\b", r"\berc-?721\b"]},
            {"name": "EVM & Ethereum Architecture", "patterns": [r"\bevm\b", r"\bethereum\b", r"\bgas optimization\b", r"\bpolygon\b"]},
            {"name": "Web3.js / Ethers.js", "patterns": [r"\bweb3\.js\b", r"\bethers(?:\.js)?\b", r"\bwagmi\b", r"\bviem\b"]},
            {"name": "Hardhat & Foundry", "patterns": [r"\bhardhat\b", r"\bfoundry\b", r"\btruffle\b"]},
            {"name": "Decentralized Storage (IPFS / Arweave)", "patterns": [r"\bipfs\b", r"\barweave\b", r"\bfilecoin\b"]},
            {"name": "DeFi & Tokenomics", "patterns": [r"\bdefi\b", r"\bamm\b", r"\bstaking\b", r"\byield farming\b"]},
            {"name": "Security Auditing & Reentrancy", "patterns": [r"\breentrancy\b", r"\bslither\b", r"\bmythril\b", r"\bsmart contract audit\b"]}
        ]
    }
}

# ─── ACTIONABLE BLUEPRINTS & HELPING HAND DATA ──────────────────────────────
SKILL_BLUEPRINTS = {
    "React & Next.js": {
        "bullets": [
            "Architected a responsive single-page platform using React and Next.js, cutting initial page load time by [40%] via server-side rendering (SSR) and dynamic code splitting.",
            "Engineered modular frontend components handling [5,000+] daily active sessions with optimized React hooks and zero layout shifts."
        ],
        "project": {
            "title": "Full-Stack SaaS Analytics Platform with Next.js 14 & Tailwind CSS",
            "desc": "Modern server-rendered portal with OAuth authentication, real-time analytics graphs, and Stripe billing.",
            "deliverables": "GitHub repository with App Router, Vercel deployment, and 100% responsive design.",
            "tech": "Next.js, TypeScript, Tailwind CSS, Prisma, PostgreSQL"
        },
        "certifications": ["Meta Front-End Developer Professional Certificate (Coursera)", "HackerRank React Verified Skill Badge"],
        "course_code": "DS404 / Web Tech",
        "course_name": "Web Applications & Full Stack Engineering",
        "tip": "Build responsive React components with custom hooks in the Web Engineering Lab."
    },
    "Docker & Containers": {
        "bullets": [
            "Containerized multi-tier microservices application using Docker and Docker Compose, reducing developer onboarding time from [3 days] to [15 minutes].",
            "Constructed multi-stage Docker build pipelines, compressing production container image footprint by [65%] from [850MB] to [280MB]."
        ],
        "project": {
            "title": "Containerized Microservices Cluster with Docker Compose",
            "desc": "Distributed backend separating auth, API gateway, and database with volume mounts and automated health checks.",
            "deliverables": "Multi-stage Dockerfile, docker-compose.yml configuration, and automated test container.",
            "tech": "Docker, Docker Compose, Nginx, Node.js, Redis"
        },
        "certifications": ["Docker Certified Associate (DCA)", "Linux Foundation Container Fundamentals (LFS158x)"],
        "course_code": "CCS",
        "course_name": "Cloud Computing & Services",
        "tip": "Containerize your academic mini-project and write multi-stage Dockerfiles."
    },
    "Large Language Models (LLMs)": {
        "bullets": [
            "Constructed an intelligent domain-specific Q&A pipeline using Llama-3 and LangChain, achieving [92%] retrieval accuracy across [5,000+] internal technical documents.",
            "Integrated asynchronous streaming responses with FastAPI, decreasing perceived first-token latency by [55%] for end users."
        ],
        "project": {
            "title": "Enterprise Retrieval-Augmented Generation (RAG) Engine with Pinecone & LangChain",
            "desc": "Conversational document assistant supporting PDF chunking, hybrid semantic search, and streaming LLM answers.",
            "deliverables": "FastAPI backend, Streamlit/React frontend, and vector database index.",
            "tech": "Python, LangChain, OpenAI / Llama-3, Pinecone, FastAPI"
        },
        "certifications": ["DeepLearning.AI: LangChain for LLM Application Development", "AWS Generative AI with LLMs Badge"],
        "course_code": "ML-II / Elective",
        "course_name": "Generative AI & Modern LLM Architectures",
        "tip": "Implement a RAG pipeline leveraging ChromaDB and open-source Hugging Face embeddings."
    },
    "RAG (Retrieval-Augmented Generation)": {
        "bullets": [
            "Engineered an enterprise RAG knowledge engine utilizing LangChain and FAISS, reducing query hallucination rate by [75%] on compliance documentation.",
            "Implemented recursive character chunking and reciprocal rank fusion (RRF), elevating context relevance scores to [0.94 NDCG]."
        ],
        "project": {
            "title": "Academic Research Paper RAG Assistant with Hybrid Search",
            "desc": "Automated ingestion pipeline parsing IEEE/arXiv PDFs, indexing dense embeddings, and providing verified citations.",
            "deliverables": "Complete vector pipeline with metadata filtering and hallucination guardrails.",
            "tech": "Python, LlamaIndex, ChromaDB, Sentence-Transformers, Streamlit"
        },
        "certifications": ["DeepLearning.AI: Advanced Retrieval for AI with Chroma", "Hugging Face Open-Source AI Campus Course"],
        "course_code": "DS404",
        "course_name": "Applied Artificial Intelligence",
        "tip": "Connect vector embeddings with cross-encoder re-ranking for top-5 accuracy."
    },
    "Vector Databases (Pinecone / Chroma / FAISS)": {
        "bullets": [
            "Benchmarked and deployed ChromaDB vector database index supporting [100,000+] high-dimensional text embeddings with sub-[35ms] cosine search latency.",
            "Configured persistent vector storage with automated incremental re-indexing, lowering daily synchronization costs by [40%]."
        ],
        "project": {
            "title": "High-Throughput Semantic Code Search Engine with FAISS",
            "desc": "Vectorized indexing of open-source GitHub repositories allowing natural language query lookup of functions and classes.",
            "deliverables": "Scalable FAISS vector index with REST API endpoints.",
            "tech": "Python, FAISS, PyTorch, FastAPI, Docker"
        },
        "certifications": ["Pinecone Vector Search Certification", "DeepLearning.AI: Vector Databases Fundamentals"],
        "course_code": "DS304",
        "course_name": "Advanced Database Systems",
        "tip": "Compare Cosine vs Euclidean similarity metrics in multi-dimensional space."
    },
    "Kubernetes Orchestration": {
        "bullets": [
            "Configured a Kubernetes (K8s) production cluster deploying [6] microservices with automated Horizontal Pod Autoscaling (HPA) handling [3x] traffic spikes.",
            "Authored custom Helm charts and ingress controllers with zero-downtime rolling updates and automated health probes."
        ],
        "project": {
            "title": "High-Availability Microservices Deployment on Minikube / K3s",
            "desc": "Declarative YAML manifest suite featuring Deployments, Services, ConfigMaps, Secrets, and Ingress routing.",
            "deliverables": "GitHub repository with Helm charts, Prometheus monitoring, and HPA autoscaling.",
            "tech": "Kubernetes, Helm, Minikube, Prometheus, Docker"
        },
        "certifications": ["Certified Kubernetes Administrator (CKA) / CKAD", "Linux Foundation Introduction to Kubernetes (LFS158)"],
        "course_code": "CCS",
        "course_name": "Cloud Infrastructure & DevOps",
        "tip": "Deploy a multi-pod cluster on local Minikube and test rolling updates."
    },
    "CI/CD & GitOps Automation": {
        "bullets": [
            "Architected automated GitHub Actions CI/CD workflows executing linting, unit testing, and Docker builds on every pull request, cutting build cycles by [50%].",
            "Automated continuous staging deployments with branch protection and test coverage thresholds (>85%)."
        ],
        "project": {
            "title": "Automated Multi-Stage CI/CD Quality Pipeline with GitHub Actions",
            "desc": "Pipeline automating code linting, PyTest coverage reporting, Docker Hub image publishing, and Render deployment.",
            "deliverables": ".github/workflows CI/CD YAML configurations with status badges.",
            "tech": "GitHub Actions, Docker, PyTest, Flake8, Bash"
        },
        "certifications": ["GitLab Certified Associate", "GitHub Actions Certification (Foundational)"],
        "course_code": "CCS",
        "course_name": "Cloud Computing & Services",
        "tip": "Add automated GitHub Actions to test your semester project repo on each commit."
    },
    "Terraform & Infrastructure as Code": {
        "bullets": [
            "Provisioned resilient multi-AZ AWS infrastructure using modular Terraform HCL scripts, guaranteeing 100% reproducible environments across staging and production.",
            "Implemented remote state management with S3 and DynamoDB state-locking, eliminating concurrent deployment drift."
        ],
        "project": {
            "title": "Automated Cloud VPC & Microservices Cluster with Terraform",
            "desc": "Declarative IaC codebase provisioning VPC subnets, security groups, EC2 instances, and RDS databases.",
            "deliverables": "Modular Terraform codebase with variable validation and outputs.",
            "tech": "Terraform, AWS, HCL, Bash"
        },
        "certifications": ["HashiCorp Certified: Terraform Associate (003)"],
        "course_code": "CCS",
        "course_name": "Cloud Computing & Services",
        "tip": "Write declarative Terraform scripts to provision cloud instances."
    },
    "Data Structures & Algorithms": {
        "bullets": [
            "Solved [350+] algorithmic challenges across LeetCode, HackerRank, and CodeChef, achieving a competitive rating peak of [1650+].",
            "Optimized core graph traversal and dynamic programming bottlenecks, improving computational complexity from [O(N^2)] to [O(N log N)]."
        ],
        "project": {
            "title": "Interactive Algorithm Visualizer & Pathfinding Simulator",
            "desc": "Dynamic visualizer demonstrating Dijkstra, A*, DFS, BFS, and dynamic programming memory matrices.",
            "deliverables": "Deployed web tool on GitHub Pages with benchmark stats.",
            "tech": "JavaScript, HTML5 Canvas, Algorithms, CSS"
        },
        "certifications": ["HackerRank Problem Solving (Advanced) Verified Certificate", "LeetCode 100 Days Coding Badge"],
        "course_code": "DS301 / DAA",
        "course_name": "Design & Analysis of Algorithms",
        "tip": "Solve LeetCode Top 75 questions focusing on trees, DP, and graphs."
    },
    "SQL & Relational DB": {
        "bullets": [
            "Designed 3NF normalized PostgreSQL schemas with composite indexes, reducing p95 query execution time from [1.8s] to [120ms].",
            "Authored complex analytical SQL queries using Common Table Expressions (CTEs) and window functions over [500,000+] rows."
        ],
        "project": {
            "title": "E-Commerce Database Schema & Query Optimization Benchmark",
            "desc": "Relational schema modeling orders, inventory, and transactions with transaction locks and query execution plans.",
            "deliverables": "SQL migration scripts, EXPLAIN ANALYZE benchmarks, and stored procedures.",
            "tech": "PostgreSQL, MySQL, SQL, Docker"
        },
        "certifications": ["Oracle Database SQL Certified Associate", "HackerRank SQL (Advanced) Verified"],
        "course_code": "DS304",
        "course_name": "Database Management Systems",
        "tip": "Practice complex JOINs, indexing strategies, and aggregation in MySQL/PostgreSQL."
    },
    "Solidity & Smart Contracts": {
        "bullets": [
            "Authored and deployed ERC-20 and ERC-721 smart contracts to Ethereum Sepolia testnet using Solidity and Hardhat, with [100%] test coverage.",
            "Optimized contract byte layout and storage slots, reducing gas execution consumption by [28%] per transaction."
        ],
        "project": {
            "title": "Decentralized Escrow & Token Marketplace with Solidity & Hardhat",
            "desc": "Smart contracts with reentrancy guards, multi-signature withdrawals, and automated testing.",
            "deliverables": "Verified contracts on Etherscan with Mocha/Chai test suite.",
            "tech": "Solidity, Hardhat, Ethers.js, OpenZeppelin, React"
        },
        "certifications": ["Metaschool Web3 Smart Contract Certification", "Alchemy University Certified Ethereum Developer"],
        "course_code": "IS / Elective",
        "course_name": "Blockchain & Cryptographic Architectures",
        "tip": "Audit smart contracts for reentrancy and overflow bugs using Slither."
    },
    "Selenium & Web Automation": {
        "bullets": [
            "Engineered an automated regression test suite using Selenium WebDriver and PyTest, executing [120+] test cases in under [8 minutes].",
            "Implemented Page Object Model (POM) architecture, decreasing test maintenance overhead by [45%] across UI revisions."
        ],
        "project": {
            "title": "Automated E-Commerce End-to-End Regression Framework",
            "desc": "Data-driven test framework with cross-browser execution, headless CI runs, and HTML screenshot reports.",
            "deliverables": "GitHub repository with Page Object Model and PyTest HTML reporting.",
            "tech": "Python, Selenium WebDriver, PyTest, Allure Reports"
        },
        "certifications": ["ISTQB Certified Tester (Foundation Level)", "Postman API Automation Certified Student"],
        "course_code": "DS406",
        "course_name": "Software Testing & Quality Assurance",
        "tip": "Automate student registration login and form validation with Selenium."
    }
}

WEAK_ACTION_VERBS = {
    "worked on": "architected / engineered / implemented",
    "helped with": "collaborated to deliver / co-developed",
    "helped": "facilitated / accelerated / co-engineered",
    "assisted": "collaborated on / accelerated delivery of",
    "responsible for": "orchestrated / spearheaded / governed",
    "handled": "streamlined / resolved / optimized",
    "did": "executed / implemented / achieved",
    "made": "engineered / constructed / deployed",
    "tried": "benchmarked / evaluated",
    "learned": "mastered / integrated",
    "participated in": "contributed to / collaborated across",
    "looked at": "analyzed / audited / evaluated"
}

FIRST_PERSON_PRONOUNS = ["i", "me", "my", "myself", "we", "our", "ours"]

ACTION_VERBS = [
    "architected", "engineered", "developed", "implemented", "designed", "deployed",
    "optimized", "accelerated", "reduced", "scaled", "automated", "built", "spearheaded",
    "refactored", "integrated", "orchestrated", "migrated", "configured", "debugged",
    "published", "maintained", "analyzed", "streamlined", "enhanced", "resolved",
    "benchmark", "benchmarked", "transformed", "containerized", "secured", "modeled"
]

SAMPLE_RESUME_TEXT = """RISHABH SHARMA
Shirpur, Maharashtra, India | rishabh.sharma@rcpit.ac.in | +91 98765 43210
GitHub: github.com/rishabh-sharma | LinkedIn: linkedin.com/in/rishabh-sharma

SUMMARY
Goal-oriented Computer Science Engineering student specializing in Data Science with solid foundations in Full Stack Web Development, Machine Learning pipelines, and Cloud infrastructure. Demonstrated ability to engineer scalable applications and solve complex algorithmic problems.

TECHNICAL SKILLS
- Programming Languages: Python, JavaScript, TypeScript, C++, SQL, HTML5, CSS3
- Frameworks & Libraries: React, Next.js, Node.js, Express, Flask, FastAPI, Pandas, NumPy, Scikit-Learn, PyTorch, Tailwind CSS
- Databases & Storage: PostgreSQL, MongoDB, Redis, MySQL
- Developer Tools & Cloud: Git, GitHub, Docker, Kubernetes, AWS (EC2, S3), REST APIs, Postman, Linux, Nginx, CI/CD

EDUCATION
SES's R. C. Patel Institute of Technology, Shirpur (Autonomous)
Bachelor of Technology in Computer Science & Engineering (Data Science)
CGPA: 8.75 / 10.00 | Expected Graduation: June 2027

PROJECTS
1. EduForecast — Academic Analytics & Attendance Prediction Engine
- Architected a full-stack predictive system using Flask, MongoDB, and Tailwind CSS serving 66+ active students.
- Implemented Scikit-Learn regression models predicting end-semester SGPA with 92% historical accuracy.
- Built an interactive What-If attendance solver reducing student detention risk by 35%.
- Containerized the application with Docker and configured automated CI/CD deployment pipelines.

2. Cloud-Native E-Commerce REST API
- Engineered a modular microservices backend with Node.js, Express, and PostgreSQL handling 500+ simulated req/sec.
- Integrated Redis caching layer resulting in a 40% reduction in database latency.
- Implemented secure JWT authentication and role-based access control (RBAC).

3. Autonomous Plant Disease Classification System
- Developed a deep learning convolutional neural network (CNN) using PyTorch with 94.6% validation accuracy.
- Processed and augmented 15,000+ agricultural leaf images with OpenCV and NumPy.
- Deployed a lightweight inference API with FastAPI and Docker.

ACHIEVEMENTS & CERTIFICATIONS
- Solved 350+ algorithmic problems across LeetCode and CodeChef (Peak Rating: 1650).
- AWS Certified Cloud Practitioner (Foundational) — 2026.
- 1st Place — RCPIT Annual Hackathon (Built an AI-powered Campus Safety Assistant).
"""


def extract_text_from_pdf(file_stream) -> str:
    """Extracts raw plain text from an uploaded PDF stream."""
    try:
        import pypdf
        reader = pypdf.PdfReader(file_stream)
        text_pages = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_pages.append(t)
        return "\n".join(text_pages).strip()
    except Exception as e:
        logger.warning(f"Error parsing PDF with pypdf: {e}")
        return ""


def extract_text_from_file(file_obj, filename: str) -> str:
    """Extracts text from PDF, TXT, or fallback files."""
    if not file_obj or not filename:
        return ""
    fname_lower = filename.lower()
    if fname_lower.endswith(".pdf"):
        return extract_text_from_pdf(file_obj)
    elif fname_lower.endswith(".txt") or fname_lower.endswith(".md"):
        try:
            content = file_obj.read()
            if isinstance(content, bytes):
                return content.decode("utf-8", errors="replace").strip()
            return str(content).strip()
        except Exception as e:
            logger.warning(f"Error reading text file: {e}")
            return ""
    else:
        try:
            content = file_obj.read()
            if isinstance(content, bytes):
                return content.decode("utf-8", errors="replace").strip()
            return str(content).strip()
        except Exception:
            return ""


def analyze_resume_text(resume_text: str, target_track: str = "full_stack", job_description: str = "") -> dict:
    """
    Supercharged Multi-Dimensional ATS Evaluation & Helping Hand Engine:
    1. Keyword Coverage against 10 Domain Tracks or Custom Job Description
    2. Section Completeness Audit (Contact, Summary, Education, Skills, Projects, Experience)
    3. Action Verbs / Impact Power Score
    4. Quantifiable Metrics & Google XYZ / STAR Formula Audit
    5. Weak Verb & Passive Phrasing Detection with Instant Upgrades
    6. First-Person Pronoun Penalty Detection
    7. Helping Hand Suite: Ready-to-copy bullet templates, project blueprints, and certifications.
    """
    if not resume_text or not resume_text.strip():
        return {
            "error": "Resume text could not be read or is empty. Please upload a valid PDF/text file or paste your resume.",
            "ats_score": 0.0,
            "matched_skills": [],
            "missing_skills": [],
            "recommendations": [],
            "helping_hand": []
        }

    raw_text = resume_text.strip()
    cleaned_text = raw_text.lower()
    normalized_text = re.sub(r"[^\w\+\#\.\s\-]", " ", cleaned_text)

    # ─── 1. KEYWORD MATCHING ──────────────────────────────────────────────────
    track_key = target_track if target_track in TRACK_TAXONOMY else "full_stack"
    track_info = TRACK_TAXONOMY[track_key]
    track_skills = list(track_info["skills"])

    custom_jd_mode = bool(job_description and len(job_description.strip()) > 30)

    if custom_jd_mode:
        jd_clean = job_description.lower()
        jd_skills = []
        all_known_skills = {}
        for t in TRACK_TAXONOMY.values():
            for sk in t["skills"]:
                all_known_skills[sk["name"]] = sk

        for sk_name, sk_data in all_known_skills.items():
            for pat in sk_data["patterns"]:
                if re.search(pat, jd_clean, re.IGNORECASE):
                    jd_skills.append(sk_data)
                    break

        if len(jd_skills) >= 4:
            target_skills = jd_skills
            track_title = "Custom Job Description Benchmark"
            track_desc = f"Audited against {len(target_skills)} technical requirements extracted from your provided Job Description."
        else:
            target_skills = track_skills
            track_title = track_info["title"] + " (with JD Overlay)"
            track_desc = track_info["description"]
    else:
        target_skills = track_skills
        track_title = track_info["title"]
        track_desc = track_info["description"]

    matched_skills = []
    missing_skills = []

    for skill in target_skills:
        skill_name = skill["name"]
        patterns = skill["patterns"]
        found = False
        for pat in patterns:
            if re.search(pat, normalized_text, re.IGNORECASE):
                found = True
                break
        if found:
            matched_skills.append(skill_name)
        else:
            missing_skills.append(skill_name)

    total_target = len(target_skills)
    matched_count = len(matched_skills)
    keyword_score = round((matched_count / float(total_target)) * 100.0, 1) if total_target > 0 else 0.0

    # ─── 2. SECTION COMPLETENESS AUDIT ────────────────────────────────────────
    section_checks = {
        "contact_info": bool(re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_text) and re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\b\d{10}\b", raw_text)),
        "summary_objective": bool(re.search(r"\b(summary|objective|profile|about me)\b", cleaned_text)),
        "education": bool(re.search(r"\b(education|academics|degree|bachelor|b\.tech|university|institute|cgpa)\b", cleaned_text)),
        "technical_skills": bool(re.search(r"\b(skills|technical skills|technologies|proficiencies|languages)\b", cleaned_text)),
        "projects": bool(re.search(r"\b(projects|personal projects|academic projects)\b", cleaned_text)),
        "experience_internships": bool(re.search(r"\b(experience|internship|work history|employment|certifications|achievements)\b", cleaned_text)),
    }
    sections_present = sum(1 for v in section_checks.values() if v)
    section_score = round((sections_present / float(len(section_checks))) * 100.0, 1)

    # ─── 3. ACTION VERBS / IMPACT AUDIT ───────────────────────────────────────
    found_verbs = []
    for verb in ACTION_VERBS:
        if re.search(rf"\b{verb}\b", cleaned_text):
            found_verbs.append(verb.capitalize())
    found_verbs = sorted(list(set(found_verbs)))
    impact_score = min(100.0, round((len(found_verbs) / 7.0) * 100.0, 1))

    # ─── 4. QUANTIFIABLE METRICS & STAR IMPACT AUDIT ──────────────────────────
    metrics_matches = re.findall(r"\b\d+(?:\.\d+)?%|\b\d+[kKxX]\b|\b\d+\+\b|\b\d+ (?:users|students|seconds|ms|queries|records|stars|requests|req/sec|orders)\b", raw_text)
    metric_count = len(metrics_matches)
    metrics_score = min(100.0, round((metric_count / 4.0) * 100.0, 1))

    # STAR bullet point detection (lines having an action verb + numbers/outcomes)
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    star_bullets = []
    for line in lines:
        line_lower = line.lower()
        has_verb = any(re.search(rf"\b{v}\b", line_lower) for v in ACTION_VERBS)
        has_metric = bool(re.search(r"\b\d+(?:\.\d+)?%|\b\d+\+|\b\d+[kKxX]\b|\b\d+ (?:users|seconds|ms|queries|records|students)\b", line))
        if has_verb and has_metric:
            star_bullets.append(line)

    # ─── 5. WEAK VERB DETECTION & UPGRADES ────────────────────────────────────
    detected_weak_verbs = []
    for weak_verb, replacement in WEAK_ACTION_VERBS.items():
        if re.search(rf"\b{weak_verb}\b", cleaned_text):
            detected_weak_verbs.append({
                "found": weak_verb,
                "suggestion": replacement
            })

    # ─── 6. FIRST PERSON PRONOUNS PENALTY CHECK ───────────────────────────────
    detected_pronouns = []
    for pronoun in FIRST_PERSON_PRONOUNS:
        if re.search(rf"\b{pronoun}\b", cleaned_text):
            detected_pronouns.append(pronoun)
    detected_pronouns = list(set(detected_pronouns))

    # ─── 7. FORMATTING & READABILITY AUDIT ─────────────────────────────────────
    words = raw_text.split()
    word_count = len(words)
    has_contact = bool(re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_text))
    has_links = bool(re.search(r"(?:github\.com|linkedin\.com|gitlab\.com|portfolio|http)", cleaned_text))
    bullet_points = len(re.findall(r"(?:^|\n)\s*[-•*]\s+", raw_text))

    formatting_rating = "OPTIMAL" if 350 <= word_count <= 850 else ("TOO_SHORT" if word_count < 350 else "VERBOSE")
    formatting_score = 100.0
    if formatting_rating != "OPTIMAL":
        formatting_score -= 20.0
    if not has_contact:
        formatting_score -= 25.0
    if not has_links:
        formatting_score -= 15.0
    if bullet_points < 4:
        formatting_score -= 15.0
    if detected_pronouns:
        formatting_score -= 10.0
    formatting_score = max(20.0, formatting_score)

    # ─── 8. OVERALL COMPOSITE ATS SCORE (0 - 100) ─────────────────────────────
    # Weighted: Keyword Match (45%), Sections (20%), Impact Verbs (15%), Metrics (15%), Formatting (5%)
    overall_ats = round(
        (keyword_score * 0.45) +
        (section_score * 0.20) +
        (impact_score * 0.15) +
        (metrics_score * 0.15) +
        (formatting_score * 0.05),
        1
    )
    overall_ats = min(100.0, max(0.0, overall_ats))

    # Rating label
    if overall_ats >= 82.0:
        rating_label = "EXCELLENT — Tier-1 Shortlist Ready"
        rating_color = "emerald"
        verdict = "Your resume demonstrates exceptional keyword alignment, structured technical impact, and quantifiable accomplishments. Shortlisting probability across Tier-1 recruiters is very high."
    elif overall_ats >= 65.0:
        rating_label = "COMPETITIVE — Strong Foundation"
        rating_color = "blue"
        verdict = "Solid profile with core competencies in place. Incorporating the remaining targeted technical keywords and boosting quantifiable results will push you into top candidate percentiles."
    elif overall_ats >= 45.0:
        rating_label = "DEVELOPING — Moderate Match"
        rating_color = "amber"
        verdict = "Foundational keywords are present, but key track competencies and measurable project impact numbers are missing. Follow the remedial roadmap and helping hand tools below to enhance compatibility."
    else:
        rating_label = "NEEDS ENHANCEMENT — High ATS Dropout Risk"
        rating_color = "rose"
        verdict = "Significant skill and formatting gaps detected. Recruiter ATS parsers may filter out this resume before manual human review. Restructure with the missing competencies and copyable templates below."

    # ─── 9. HELPING HAND SUITE: ACTIONABLE BLUEPRINTS ─────────────────────────
    helping_hand_list = []
    recommendations = []

    for m in missing_skills:
        bp = SKILL_BLUEPRINTS.get(m)
        if bp:
            blueprint_obj = {
                "skill": m,
                "bullet_templates": bp.get("bullets", [
                    f"Architected an end-to-end service implementing {m}, elevating processing throughput by [35%].",
                    f"Engineered and deployed robust module featuring {m}, achieving [99.5%] uptime across [5,000+] transactions."
                ]),
                "project": bp.get("project", {
                    "title": f"Production-Grade {m} Implementation",
                    "desc": f"Full-featured demonstrator showcasing best practices in {m}.",
                    "deliverables": "Open-source GitHub repository with automated tests and CI/CD.",
                    "tech": f"{m}, Python / TypeScript, Docker"
                }),
                "certifications": bp.get("certifications", ["HackerRank Skill Certification", "Coursera Guided Project Badge"]),
                "course_code": bp.get("course_code", "Technical Elective"),
                "course_name": bp.get("course_name", f"Practical {m} Systems"),
                "tip": bp.get("tip", f"Build a demonstrable GitHub repository featuring {m} to substantiate this keyword on your resume.")
            }
            helping_hand_list.append(blueprint_obj)
            recommendations.append({
                "skill": m,
                "course_code": blueprint_obj["course_code"],
                "course_name": blueprint_obj["course_name"],
                "action": blueprint_obj["tip"]
            })
        else:
            default_bp = {
                "skill": m,
                "bullet_templates": [
                    f"Engineered and benchmarked a high-throughput microservice utilizing {m}, reducing data processing latency by [30%].",
                    f"Implemented scalable architecture featuring {m}, serving [1,000+] requests/day with comprehensive unit tests."
                ],
                "project": {
                    "title": f"Scalable {m} Application Platform",
                    "desc": f"Production-grade demonstrable project implementing {m} with CI/CD and Docker containerization.",
                    "deliverables": "GitHub repository with Swagger API documentation, Dockerfile, and README architecture diagram.",
                    "tech": f"{m}, REST APIs, Docker, Git"
                },
                "certifications": [f"{m} Professional Certification", "HackerRank Verified Skill Badge"],
                "course_code": "Technical Elective",
                "course_name": f"Practical {m} Engineering",
                "tip": f"Build and host a demonstrable GitHub repository featuring {m} to substantiate this keyword on your resume."
            }
            helping_hand_list.append(default_bp)
            recommendations.append({
                "skill": m,
                "course_code": default_bp["course_code"],
                "course_name": default_bp["course_name"],
                "action": default_bp["tip"]
            })

    return {
        "target_track": track_key,
        "track_title": track_title,
        "track_description": track_desc,
        "ats_score": overall_ats,
        "rating_label": rating_label,
        "rating_color": rating_color,
        "verdict": verdict,
        "sub_scores": {
            "keyword_match": keyword_score,
            "section_completeness": section_score,
            "impact_verbs": impact_score,
            "quantifiable_metrics": metrics_score,
            "formatting": formatting_score
        },
        "matched_count": matched_count,
        "total_skills": total_target,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "action_verbs_found": found_verbs,
        "section_checks": section_checks,
        "recommendations": recommendations,
        "helping_hand": helping_hand_list,
        "weak_verbs_detected": detected_weak_verbs,
        "first_person_pronouns": detected_pronouns,
        "star_analysis": {
            "star_bullets_count": len(star_bullets),
            "sample_star_bullets": star_bullets[:3]
        },
        "custom_jd_mode": custom_jd_mode,
        "readability": {
            "word_count": word_count,
            "length_status": formatting_rating,
            "has_contact_info": has_contact,
            "has_github_or_linkedin": has_links,
            "bullet_count": bullet_points,
            "metric_count": metric_count
        }
    }
