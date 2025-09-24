import cohere
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError, ClientError, TransientError
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from core.config import neo4j_uri, neo4j_user, neo4j_password, cohere_api_key, COHERE_EMBED_MODEL
from utils.logger import SystemLogger
from utils.exceptions import DatabaseConnectionError, DatabaseQueryError, APIRequestError

# Initialize Cohere client with error handling
try:
    co = cohere.Client(cohere_api_key)
    cohere_model = COHERE_EMBED_MODEL
    SystemLogger.info("Cohere client initialized successfully", {'model': cohere_model})
except Exception as e:
    SystemLogger.error(
        "Failed to initialize Cohere client - Check API key validity",
        exception=e,
        context={'api_key_provided': bool(cohere_api_key), 'model': COHERE_EMBED_MODEL}
    )
    raise APIRequestError(f"Failed to initialize Cohere client: {e}")

class Neo4jConnector:
    """
    Neo4j graph database connector for user interactions and similarity analysis.
    
    Handles user profile storage, interaction logging, and similarity-based 
    recommendations using Neo4j graph database. Integrates with Cohere embeddings
    for vector-based user similarity calculations and collaborative filtering.
    
    Attributes
    ----------
    driver : neo4j.GraphDatabase.driver
        Neo4j database driver for graph operations
        
    Methods
    -------
    get_user_vector(education, age_group, profession, query)
        Generate user embedding vector using Cohere API
    get_similar_users(user_vector)
        Find similar users based on vector similarity
    store_interaction(user_id, education, age_group, profession, user_query, response, user_vector)
        Store user interaction and profile in graph database
    get_enrolled_courses_from_similar_users(user_ids)
        Retrieve course enrollments from similar users
        
    Raises
    ------
    DatabaseConnectionError
        If Neo4j connection cannot be established
    DatabaseQueryError
        If graph database queries fail
    APIRequestError
        If Cohere embedding generation fails
        
    Examples
    --------
    >>> connector = Neo4jConnector()
    >>> vector = connector.get_user_vector("Graduate", "26-40", "Professional", "ML query")
    >>> similar_users = connector.get_similar_users(vector)
    """
    def __init__(self):
        SystemLogger.info("Initializing Neo4j connection", {
            'uri': neo4j_uri, 'user': neo4j_user
        })
        
        try:
            self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            
            # Test connection immediately
            with self.driver.session() as session:
                session.run("RETURN 1 AS test")
                
            SystemLogger.info("Neo4j connection established successfully", {
                'uri': neo4j_uri, 'database': 'default'
            })
        except AuthError as e:
            SystemLogger.error(
                "Neo4j authentication failed - Check username and password",
                exception=e,
                context={'uri': neo4j_uri, 'user': neo4j_user}
            )
            raise DatabaseConnectionError(f"Neo4j authentication failed: {e}")
        except ServiceUnavailable as e:
            SystemLogger.error(
                "Neo4j service unavailable - Check if Neo4j server is running and accessible",
                exception=e,
                context={'uri': neo4j_uri}
            )
            raise DatabaseConnectionError(f"Neo4j service unavailable: {e}")
        except Exception as e:
            SystemLogger.error(
                "Failed to establish Neo4j connection - Check server status and network connectivity",
                exception=e,
                context={'uri': neo4j_uri, 'user': neo4j_user}
            )
            raise DatabaseConnectionError(f"Neo4j connection failed: {e}")

    def store_interaction(self, user_id, education, age_group, profession, user_query, response, user_vector):
        SystemLogger.debug("Storing user interaction in Neo4j", {
            'user_id': user_id, 'education': education, 'age_group': age_group, 'profession': profession
        })

        try:
            with self.driver.session() as session:
                session.execute_write(
                    self._create_interaction, user_id, education, age_group, profession, user_query, response, user_vector
                )
            SystemLogger.info("User interaction stored successfully in Neo4j", {
                'user_id': user_id, 'query_preview': user_query[:100] if user_query else 'N/A'
            })
        except ClientError as e:
            SystemLogger.error(
                "Neo4j client error while storing interaction - Check Cypher query syntax",
                exception=e,
                context={
                    'user_id': user_id,
                    'cypher_error_code': getattr(e, 'code', 'unknown'),
                    'query_preview': user_query[:100] if user_query else 'N/A'
                }
            )
            raise DatabaseQueryError(f"Failed to store interaction: {e}")
        except TransientError as e:
            SystemLogger.error(
                "Neo4j transient error while storing interaction - Temporary database issue, retry may succeed",
                exception=e,
                context={'user_id': user_id}
            )
            raise DatabaseQueryError(f"Transient error storing interaction: {e}")
        except Exception as e:
            SystemLogger.error(
                "Unexpected error storing Neo4j interaction",
                exception=e,
                context={'user_id': user_id, 'education': education, 'age_group': age_group}
            )
            raise DatabaseQueryError(f"Failed to store interaction: {e}")

    @staticmethod
    def _create_interaction(tx, user_id, education, age_group, profession, user_query, response, user_vector):
        tx.run("""
            MERGE (u:User {id: $user_id})
            SET u.education = $education,
                u.age_group = $age_group,
                u.profession = $profession
            CREATE (i:Interaction {
                query: $user_query,
                response: $response,
                user_vector: $user_vector
            })
            MERGE (u)-[:MADE]->(i)
        """, user_id=user_id,
             education=education,
             age_group=age_group,
             profession=profession,
             user_query=user_query,
             response=response,
             user_vector=user_vector)

    def get_all_user_vectors(self):
     with self.driver.session() as session:
        return session.execute_read(self._get_all_user_vectors)

    @staticmethod
    def _get_all_user_vectors(tx):
      query = """
        MATCH (u:User)-[:MADE]->(i:Interaction)
        WHERE i.user_vector IS NOT NULL
        RETURN u.id AS user_id, i.query AS query, i.user_vector AS user_vector
    """
      result = tx.run(query)
      return [
        {
            "user_id": record["user_id"],
            "query": record["query"],
            "user_vector": record["user_vector"]
        }
        for record in result
      ]
    def get_user_vector(self, education, age_group, profession, user_query):
        SystemLogger.debug("Generating user vector with Cohere", {
            'education': education, 'age_group': age_group, 'profession': profession
        })
        
        profile_text = (
            f"User with {education} education, aged {age_group}, "
            f"working at {profession} level. Recently asked: '{user_query}'"
        )
        
        try:
            response = co.embed(
                texts=[profile_text],
                model=cohere_model,
                input_type="clustering"
            )
            
            if not response.embeddings or not response.embeddings[0]:
                SystemLogger.error(
                    "Cohere API returned empty embeddings - Check input text and model availability",
                    context={'profile_text': profile_text, 'model': cohere_model}
                )
                raise APIRequestError("Cohere returned empty embeddings")
            
            SystemLogger.debug("User vector generated successfully", {
                'vector_dimension': len(response.embeddings[0]),
                'model': cohere_model
            })
            return response.embeddings[0]
            
        except cohere.errors.CohereAPIError as e:
            SystemLogger.error(
                "Cohere API error while generating embeddings - Check API key and quota limits",
                exception=e,
                context={
                    'profile_text': profile_text,
                    'model': cohere_model,
                    'api_error_code': getattr(e, 'status_code', 'unknown')
                }
            )
            raise APIRequestError(f"Cohere API error: {e}")
        except Exception as e:
            SystemLogger.error(
                "Unexpected error generating user vector with Cohere",
                exception=e,
                context={'profile_text': profile_text, 'model': cohere_model}
            )
            raise APIRequestError(f"Failed to generate user vector: {e}")

    def get_similar_users(self, user_vector, top_n=5):
        SystemLogger.info("Computing user similarity vectors for collaborative filtering", {
            'top_n': top_n, 'input_vector_dimension': len(user_vector) if user_vector else 0
        })

        try:
            all_users = self.get_all_user_vectors()
            if not all_users:
                SystemLogger.info("No existing user vectors found in Neo4j database")
                return []

            SystemLogger.info(f"Retrieved {len(all_users)} users with interaction vectors for similarity computation")
            
            similarities = []
            failed_computations = 0

            for user in all_users:
                try:
                    if not user.get("user_vector"):
                        SystemLogger.debug(f"Skipping user with empty vector", {'user_id': user.get('user_id')})
                        continue
                        
                    similarity = cosine_similarity([user_vector], [user["user_vector"]])
                    similarities.append({
                        "user_id": user["user_id"],
                        "query": user["query"],
                        "score": similarity[0][0]
                    })
                except Exception as e:
                    failed_computations += 1
                    SystemLogger.debug(f"Failed to compute similarity for user", {
                        'user_id': user.get('user_id'), 'error': str(e)
                    })

            if failed_computations > 0:
                SystemLogger.info(f"Some similarity computations failed", {
                    'failed_count': failed_computations, 'successful_count': len(similarities)
                })

            similarities.sort(key=lambda x: x["score"], reverse=True)
            result = similarities[:top_n]

            if result:
                similar_user_ids = [user['user_id'] for user in result]
                SystemLogger.info(f"Found {len(result)} similar users for collaborative recommendations", {
                    'similar_user_ids': similar_user_ids,
                    'similarity_scores': [round(user['score'], 3) for user in result],
                    'total_computed': len(similarities)
                })
            else:
                SystemLogger.info("No similar users found - will use general recommendations")

            return result
            
        except Exception as e:
            SystemLogger.error(
                "Failed to compute user similarities - Error in vector computation or database query",
                exception=e,
                context={'top_n': top_n, 'vector_provided': user_vector is not None}
            )
            raise DatabaseQueryError(f"Failed to compute user similarities: {e}")

    def get_recommendations_for_user(self, query):
        with self.driver.session() as session:
            return session.execute_read(self._get_recommendations_for_user, query)

    @staticmethod
    def _get_recommendations_for_user(tx, query):
        result = tx.run("""
            MATCH (i:Interaction {query: $query})
            RETURN i.response AS response
        """, {"query": query})
        return [record["response"] for record in result]

    def get_enrolled_courses_from_similar_users(self, user_ids):
        SystemLogger.info(f"Searching for enrolled courses from similar users: {user_ids}")

        with self.driver.session() as session:
            enrolled_courses = session.execute_read(self._get_enrolled_courses_from_similar_users, user_ids)

            if enrolled_courses:
                SystemLogger.info(f"Found {len(enrolled_courses)} courses from similar users' enrollments: {enrolled_courses}")
            else:
                SystemLogger.info(f"No enrolled courses found for similar users {user_ids}")

            return enrolled_courses

    @staticmethod
    def _get_enrolled_courses_from_similar_users(tx, user_ids):
        query = """
        MATCH (u:User)-[:ENROLLED_IN]->(c:Course)
        WHERE u.id IN $user_ids
        RETURN DISTINCT c.name AS course
        """
        result = tx.run(query, user_ids=user_ids)
        return [record["course"] for record in result]

    def initialize_course_data(self, mysql_connector):
        """
        Initialize Neo4j with course data from MySQL.
        Creates Course nodes and sample user enrollments.
        """
        try:
            SystemLogger.info("Starting Neo4j course data initialization")

            # Get course data from MySQL
            courses = mysql_connector.get_courses()
            SystemLogger.info(f"Retrieved {len(courses)} course records from MySQL")

            # Log sample data structure
            if courses:
                SystemLogger.debug(f"Sample course data structure: {courses[0]}")
                SystemLogger.debug(f"Available fields: {list(courses[0].keys())}")

            with self.driver.session() as session:
                # First, create Course nodes from unique course names
                unique_courses = {}
                for course in courses:
                    course_name = course.get('course_name', 'Unknown')
                    if course_name not in unique_courses:
                        unique_courses[course_name] = {
                            'name': course_name,
                            'description': course.get('module_summary', '')[:200]  # Use first module summary as description
                        }

                SystemLogger.info(f"Identified {len(unique_courses)} unique courses to create")
                SystemLogger.debug(f"Unique course names: {list(unique_courses.keys())}")

                # Create Course nodes
                courses_created = 0
                for course_name, course_data in unique_courses.items():
                    result = session.run("""
                        MERGE (c:Course {name: $course_name})
                        SET c.description = $description
                        RETURN c.name as name
                    """, {
                        "course_name": course_data['name'],
                        "description": course_data['description']
                    })
                    record = result.single()
                    if record:
                        courses_created += 1
                        SystemLogger.debug(f"Created/Updated Course node: {record['name']}")
                    else:
                        SystemLogger.error(f"Failed to create Course node: {course_name}")

                SystemLogger.info(f"Successfully created {courses_created} Course nodes")

                # Get actual course names for sample enrollments
                actual_course_names = [course.get('course_name', '') for course in courses if course.get('course_name')]
                # Get unique course names only
                actual_course_names = list(set(actual_course_names))
                SystemLogger.info(f"Preparing to create sample enrollments with {len(actual_course_names)} unique courses")
                SystemLogger.debug(f"Available course names for enrollment: {actual_course_names}")
                sample_enrollments = []

                # Create sample user enrollments using actual course names
                if len(actual_course_names) >= 2:
                    SystemLogger.info(f"Creating sample enrollments (have {len(actual_course_names)} courses, need at least 2)")
                    sample_enrollments = [
                        {"user_id": "student_001", "education": "Undergraduate",
                         "courses": actual_course_names[:2]},  # First 2 courses
                        {"user_id": "student_002", "education": "Graduate",
                         "courses": actual_course_names[2:4] if len(actual_course_names) > 3 else actual_course_names[:2]},
                        {"user_id": "student_003", "education": "PhD",
                         "courses": actual_course_names[4:6] if len(actual_course_names) > 5 else actual_course_names[:2]},
                        {"user_id": "professional_001", "education": "Graduate",
                         "courses": actual_course_names[6:8] if len(actual_course_names) > 7 else actual_course_names[:2]},
                        {"user_id": "professional_002", "education": "Undergraduate",
                         "courses": actual_course_names[:2]}  # Same as student_001
                    ]

                    SystemLogger.info(f"Creating sample enrollments for {len(sample_enrollments)} users")

                    users_created = 0
                    enrollments_created = 0

                    for enrollment in sample_enrollments:
                        user_id = enrollment["user_id"]
                        user_courses = enrollment["courses"]

                        # Create user if not exists
                        user_result = session.run("""
                            MERGE (u:User {id: $user_id})
                            SET u.education = $education
                            RETURN u.id as id
                        """, {
                            "user_id": user_id,
                            "education": enrollment["education"]
                        })

                        user_record = user_result.single()
                        if user_record:
                            users_created += 1

                        # Create enrollment relationships
                        for course_name in user_courses:
                            enrollment_result = session.run("""
                                MATCH (u:User {id: $user_id})
                                MATCH (c:Course {name: $course_name})
                                MERGE (u)-[:ENROLLED_IN]->(c)
                                RETURN u.id as user, c.name as course
                            """, {
                                "user_id": user_id,
                                "course_name": course_name
                            })

                            enrollment_record = enrollment_result.single()
                            if enrollment_record:
                                enrollments_created += 1

                    SystemLogger.info(f"Created {users_created} sample users with {enrollments_created} course enrollments")

                else:
                    SystemLogger.info(f"Skipping enrollment creation - only {len(actual_course_names)} courses available (need at least 2)")

                # Final validation - check what's actually in the graph with separate simple queries
                actual_courses = session.run("MATCH (c:Course) RETURN count(c) as count").single()['count']
                actual_users = session.run("MATCH (u:User) RETURN count(u) as count").single()['count']
                actual_enrollments = session.run("MATCH ()-[r:ENROLLED_IN]->() RETURN count(r) as count").single()['count']

                SystemLogger.info("Neo4j graph validation after initialization", {
                    'actual_courses_in_graph': actual_courses,
                    'actual_users_in_graph': actual_users,
                    'actual_enrollments_in_graph': actual_enrollments,
                    'expected_courses': len(unique_courses),
                    'expected_users': len(sample_enrollments) if sample_enrollments else 0
                })

                if actual_enrollments == 0 and len(sample_enrollments) > 0:
                    SystemLogger.error("No enrollment relationships created during initialization")
                elif actual_enrollments > 0:
                    SystemLogger.info(f"Successfully created {actual_enrollments} ENROLLED_IN relationships")

                SystemLogger.info("Neo4j course data initialization completed", {
                    'courses_attempted': len(unique_courses),
                    'enrollments_attempted': len(sample_enrollments)
                })

        except Exception as e:
            SystemLogger.error(
                "Failed to initialize Neo4j course data",
                exception=e,
                context={'mysql_data_available': courses is not None}
            )
            raise DatabaseQueryError(f"Failed to initialize course data: {e}")


