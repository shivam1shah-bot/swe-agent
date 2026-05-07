from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from typing import Dict, Any

class GoogleDriveService:
    def __init__(self, config: Dict[str, Any]):
        # Below is for google oauth
        # Expect config to be the google_api subsection (already unwrapped)
        self.client_id = config['client_id']
        self.client_secret = config['client_secret']
        self.redirect_uris = config['redirect_uris']
        self.scopes = config['scopes']
        self.auth_uri = config['auth_uri']
        self.token_uri = config['token_uri']
        
        # Initialize credentials to None
        self.credentials = None

        # Below is for google service account
        # self.credentials = Credentials.from_service_account_file(
        #     config['google_api']['credentials_json'], 
        #     scopes=['https://www.googleapis.com/auth/documents.readonly'])


    def authenticate(self):
        # Set up the OAuth flow for web applications
        from google_auth_oauthlib.flow import Flow
        from google.auth.transport.requests import Request
        
        # Create the flow with proper configuration
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uris": self.redirect_uris,
                    "auth_uri": self.auth_uri,
                    "token_uri": self.token_uri
                }
            },
            scopes=self.scopes,
            redirect_uri=self.redirect_uris[0]
        )
        
        # Generate the authorization URL
        auth_url, _ = flow.authorization_url(prompt='consent')

        # Return the authorization URL
        return auth_url

    def exchange_code_for_token(self, code: str):
        # Use the code to fetch the token
        from google_auth_oauthlib.flow import Flow
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uris": self.redirect_uris,
                    "auth_uri": self.auth_uri,
                    "token_uri": self.token_uri
                }
            },
            scopes=self.scopes,
            redirect_uri=self.redirect_uris[0]
        )

        # Exchange the authorization code for credentials
        try:
            flow.fetch_token(code=code)
        except Exception as e:
            if "invalid_grant" in str(e).lower():
                raise Exception("Authorization code is invalid, expired, or has already been used. Please try the OAuth flow again.")
            else:
                raise Exception(f"Failed to exchange authorization code for token: {str(e)}")

        # Store the credentials
        self.credentials = flow.credentials

    def get_file_content(self, file_id: str, mime_type: str = 'text/plain') -> str:
        service = build('drive', 'v3', credentials=self.credentials)
        request = service.files().export_media(fileId=file_id, mimeType=mime_type)
        file_content = request.execute()
        return file_content.decode('utf-8')

    def get_google_doc_content(self, file_id: str) -> str:
        """
        Get content from a Google Doc using the Google Docs API.
        
        Args:
            file_id: The Google Doc file ID
            
        Returns:
            The document content as plain text with embedded images
        """
        try:
            # Build the Google Docs API service
            docs_service = build('docs', 'v1', credentials=self.credentials)
            
            # Get the document
            document = docs_service.documents().get(documentId=file_id).execute()
            
            # Extract text content from the document structure
            content = document.get('body', {}).get('content', [])
            
            # Extract text and images
            text_content, images = self._extract_text_and_images_from_document_content(content, file_id)
            
            # Try selective image extraction - only architecture-related images or limit to 3
            if not images:
                try:
                    images = self._extract_selective_images(file_id)
                except Exception as e:
                    images = {}
            
            # Add image references to the content in the format expected by PRD parser
            if images:
                # Add image references at the end of the content
                text_content += "\n\n<!-- Image References -->\n"
                for i, (image_id, base64_data) in enumerate(images.items(), 1):
                    text_content += f"\n[image{i}]: <{base64_data}>\n"
                
                # Also add image references in architecture-related sections
                # Look for architecture-related content and add image references there
                architecture_keywords = ["current architecture", "system architecture", "architecture", "current system"]
                for keyword in architecture_keywords:
                    if keyword.lower() in text_content.lower():
                        # Find the section and add image reference
                        import re
                        pattern = rf"({keyword}[^.]*\.)"
                        match = re.search(pattern, text_content, re.IGNORECASE)
                        if match:
                            # Add image reference after the architecture section
                            section_end = match.end()
                            image_ref = f"\n\n![][image1]\n"
                            text_content = text_content[:section_end] + image_ref + text_content[section_end:]
                            break
            
            return text_content
        except Exception as e:
            raise Exception(f"Error fetching Google Doc content: {str(e)}")
    
    def _extract_text_and_images_from_document_content(self, content: list, file_id: str) -> tuple[str, dict]:
        """
        Extract text and images from Google Docs document content structure.
        
        Args:
            content: The content array from Google Docs API
            file_id: The Google Doc file ID for image extraction
            
        Returns:
            Tuple of (plain text content, dictionary of image_id -> base64_data)
        """
        import base64
        
        text_parts = []
        images = {}
        image_counter = 1
        
        for element in content:
            if 'paragraph' in element:
                paragraph = element['paragraph']
                for text_run in paragraph.get('elements', []):
                    if 'textRun' in text_run:
                        text_content = text_run['textRun'].get('content', '')
                        text_parts.append(text_content)
                    elif 'inlineObjectElement' in text_run:
                        # Handle inline images
                        inline_obj = text_run['inlineObjectElement']
                        inline_object_id = inline_obj.get('inlineObjectId')
                        if inline_object_id:
                            try:
                                # Get the inline object (image)
                                inline_object = self._get_inline_object(file_id, inline_object_id)
                                if inline_object:
                                    # Extract image data and convert to base64
                                    image_data = self._extract_image_data(inline_object)
                                    if image_data:
                                        base64_data = f"data:image/png;base64,{base64.b64encode(image_data).decode('utf-8')}"
                                        images[f"image{image_counter}"] = base64_data
                                        # Add image reference in the text
                                        text_parts.append(f"\n![][image{image_counter}]\n")
                                        image_counter += 1
                            except Exception as e:
                                print(f"Error extracting inline image: {str(e)}")
                                # Continue processing other content
            elif 'table' in element:
                # Handle tables - extract text from table cells
                table = element['table']
                for row in table.get('tableRows', []):
                    for cell in row.get('tableCells', []):
                        for cell_content in cell.get('content', []):
                            if 'paragraph' in cell_content:
                                for text_run in cell_content['paragraph'].get('elements', []):
                                    if 'textRun' in text_run:
                                        text_content = text_run['textRun'].get('content', '')
                                        text_parts.append(text_content)
        
        return ''.join(text_parts), images
    
    def _get_inline_object(self, file_id: str, inline_object_id: str) -> dict:
        """
        Get inline object (image) from Google Docs.
        
        Args:
            file_id: The Google Doc file ID
            inline_object_id: The inline object ID
            
        Returns:
            Inline object data
        """
        try:
            docs_service = build('docs', 'v1', credentials=self.credentials)
            inline_object = docs_service.documents().inlineObjects().get(
                documentId=file_id,
                objectId=inline_object_id
            ).execute()
            return inline_object
        except Exception as e:
            print(f"Error getting inline object: {str(e)}")
            return None
    
    def _extract_image_data(self, inline_object: dict) -> bytes:
        """
        Extract image data from inline object.
        
        Args:
            inline_object: The inline object data from Google Docs API
            
        Returns:
            Image data as bytes
        """
        try:
            # Navigate through the inline object structure to get image data
            embedded_object = inline_object.get('inlineObjectProperties', {}).get('embeddedObject', {})
            image_properties = embedded_object.get('imageProperties', {})
            content_uri = image_properties.get('contentUri')
            
            if content_uri:
                # Download the image from the content URI
                drive_service = build('drive', 'v3', credentials=self.credentials)
                # Extract file ID from content URI
                file_id = content_uri.split('/')[-1]
                request = drive_service.files().get_media(fileId=file_id)
                image_data = request.execute()
                return image_data
        except Exception as e:
            print(f"Error extracting image data: {str(e)}")
        
        return None


    def _extract_selective_images(self, file_id: str) -> dict:
        """
        Extract only architecture-related images or limit to first 1 images.
        
        Args:
            file_id: The Google Doc file ID
            
        Returns:
            Dictionary of image_id -> base64_data
        """
        import base64
        import re
        
        try:
            print("Starting selective image extraction...")
            
            # Try to export as HTML
            drive_service = build('drive', 'v3', credentials=self.credentials)
            
            try:
                request = drive_service.files().export_media(fileId=file_id, mimeType='text/html')
                html_content = request.execute().decode('utf-8')
                print(f"HTML content length: {len(html_content)}")
                
                # Find img tags with src attributes
                img_pattern = r'<img[^>]+src="([^"]+)"[^>]*>'
                img_matches = re.findall(img_pattern, html_content, re.IGNORECASE)
                print(f"Found {len(img_matches)} total images in HTML")
                
                # Limit to first 1 images to avoid timeout (reduced from 3 for faster processing)
                img_matches = img_matches[:1]
                print(f"Processing {len(img_matches)} images (limited to 2 for faster processing)")
                
                images = {}
                image_counter = 1
                
                for img_src in img_matches:
                    print(f"Processing image {image_counter}: {img_src[:50]}...")
                    
                    # If it's a data URI, extract it
                    if img_src.startswith('data:image/'):
                        images[f"image{image_counter}"] = img_src
                        image_counter += 1
                        print(f"Added data URI image {image_counter-1}")
                    # If it's a Google Drive URL, try to download it with timeout
                    elif 'googleusercontent.com' in img_src:
                        try:
                            # Use requests to download with OAuth token and short timeout
                            import requests
                            headers = {
                                'Authorization': f'Bearer {self.credentials.token}'
                            }
                            response = requests.get(img_src, headers=headers, timeout=5)  # 5 second timeout
                            if response.status_code == 200:
                                img_data = response.content
                                base64_data = f"data:image/png;base64,{base64.b64encode(img_data).decode('utf-8')}"
                                images[f"image{image_counter}"] = base64_data
                                image_counter += 1
                                print(f"Successfully downloaded image {image_counter-1}")
                            else:
                                print(f"Failed to download image: {response.status_code}")
                        except requests.exceptions.Timeout:
                            print(f"Timeout downloading image {image_counter}, skipping...")
                        except Exception as e:
                            print(f"Error downloading image {image_counter}: {str(e)}")
                    
                    # Stop if we've processed 3 images
                    if image_counter > 3:
                        break
                
                return images
                
            except Exception as e:
                print(f"Error in selective image extraction: {str(e)}")
                return {}
                
        except Exception as e:
            print(f"Error in selective image extraction: {str(e)}")
            return {}
