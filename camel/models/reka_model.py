# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING


from camel.configs import REKA_API_PARAMS
from camel.messages import OpenAIMessage
from camel.models import BaseModelBackend
from camel.types import ChatCompletion, ModelType
from camel.utils import (
    BaseTokenCounter,
    OpenAITokenCounter,
    api_keys_required,
)

if TYPE_CHECKING:
    from reka.types import ChatResponse, ChatMessage

try:
    import os

    if os.getenv("AGENTOPS_API_KEY") is not None:
        from agentops import LLMEvent, record
    else:
        raise ImportError
except (ImportError, AttributeError):
    LLMEvent = None


class RekaModel(BaseModelBackend):
    r"""Reka API in a unified BaseModelBackend interface."""

    def __init__(
        self,
        model_type: ModelType,
        model_config_dict: Dict[str, Any],
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        token_counter: Optional[BaseTokenCounter] = None,
    ) -> None:
        r"""Constructor for Reka backend.

        Args:
            model_type (ModelType): Model for which a backend is created,
                one of REKA_* series.
            model_config_dict (Dict[str, Any]): A dictionary that will
                be fed into `Reka.chat.create`.
            api_key (Optional[str]): The API key for authenticating with the
                Reka service. (default: :obj:`None`)
            url (Optional[str]): The url to the Reka service.
            token_counter (Optional[BaseTokenCounter]): Token counter to use
                for the model. If not provided, `OpenAITokenCounter` will be
                used.
        """
        super().__init__(
            model_type, model_config_dict, api_key, url, token_counter
        )
        self._api_key = api_key or os.environ.get("REKA_API_KEY")
        self._url = url or os.environ.get("REKA_SERVER_URL")

        from reka.client import Reka

        self._client = Reka(api_key=self._api_key, base_url=self._url)
        self._token_counter: Optional[BaseTokenCounter] = None

    def _to_openai_response(
        self, response: 'ChatResponse'
    ) -> ChatCompletion:

        obj = ChatCompletion.construct(
            id=response.id,
            choices=[
                dict(
                    message={
                        "role": response.responses[0].message.role,  # type: ignore[index,union-attr]
                        "content": response.responses[0].message.content,  # type: ignore[index,union-attr]
                    },
                    finish_reason=response.responses[0].finish_reason  # type: ignore[index]
                    if response.responses[0].finish_reason  # type: ignore[index]
                    else None,
                )
            ],
            created=None,
            model=response.model,
            object="chat.completion",
            usage=response.usage,
        )

        return obj

    def _to_reka_chatmessage(
        self,
        messages: List[OpenAIMessage],
    ) -> List["ChatMessage"]:

        new_messages = []
        for msg in messages:

            role = msg.get("role")
            content = msg.get("content")

            if role == "user":
                new_messages.append(ChatMessage(Content=content,
                                                ChatRole="user"))  # type: ignore[arg-type]
            elif role == "assistant":
                new_messages.append(
                    ChatMessage(Content=content,
                                ChatRole="assistant")  # type: ignore[arg-type]
                )
            elif role == "system":
                new_messages.append(ChatMessage(Content=content,
                                                ChatRole="assistant"))  # type: ignore[arg-type]
            else:
                raise ValueError(f"Unsupported message role: {role}")

        return new_messages  # type: ignore[return-value]

    @property
    def token_counter(self) -> BaseTokenCounter:
        r"""Initialize the token counter for the model backend.

        # NOTE: Temporarily using `OpenAITokenCounter`

        Returns:
            BaseTokenCounter: The token counter following the model's
                tokenization style.
        """
        if not self._token_counter:
            self._token_counter = OpenAITokenCounter(
                model=ModelType.GPT_4O_MINI
            )
        return self._token_counter

    @api_keys_required("REKA_API_KEY")
    def run(
        self,
        messages: List[OpenAIMessage],
    ) -> ChatCompletion:
        r"""Runs inference of Mistral chat completion.

        Args:
            messages (List[OpenAIMessage]): Message list with the chat history
                in OpenAI API format.

        Returns:
            ChatCompletion.
        """
        reka_messages = self._to_reka_chatmessage(messages)

        response = self._client.chat.create(
            messages=reka_messages,
            model=self.model_type.value,
            **self.model_config_dict,
        )

        openai_response = self._to_openai_response(response)  # type: ignore[arg-type]

        # Add AgentOps LLM Event tracking
        if LLMEvent:
            llm_event = LLMEvent(
                thread_id=openai_response.id,
                prompt=" ".join(
                    [message.get("content") for message in messages]  # type: ignore[misc]
                ),
                prompt_tokens=openai_response.usage.input_tokens,  # type: ignore[union-attr]
                completion=openai_response.choices[0].message.content,
                completion_tokens=openai_response.usage.output_tokens,  # type: ignore[union-attr]
                model=self.model_type.value,
            )
            record(llm_event)

        return openai_response

    def check_model_config(self):
        r"""Check whether the model configuration contains any
        unexpected arguments to Reka API.

        Raises:
            ValueError: If the model configuration dictionary contains any
                unexpected arguments to Reka API.
        """
        for param in self.model_config_dict:
            if param not in REKA_API_PARAMS:
                raise ValueError(
                    f"Unexpected argument `{param}` is "
                    "input into Reka model backend."
                )

    @property
    def stream(self) -> bool:
        r"""Returns whether the model is in stream mode, which sends partial
        results each time. Current it's not supported.

        Returns:
            bool: Whether the model is in stream mode.
        """
        return False
