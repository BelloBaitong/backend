import { Injectable, InternalServerErrorException } from '@nestjs/common';

type RagHistoryItem = {
  role: 'user' | 'assistant';
  content: string;
};

type RagAnswerOptions = {
  chatHistory?: RagHistoryItem[];
  sessionContext?: Record<string, any> | null;
};

@Injectable()
export class RecommendationService {
  private readonly ragBaseUrl = process.env.RAG_SERVICE_URL;

  async ragAnswer(
    queryText: string,
    topK: number = 8,
    userId: number,
    options: RagAnswerOptions = {},
  ) {
    if (!this.ragBaseUrl) {
      throw new InternalServerErrorException('RAG_SERVICE_URL is not configured');
    }

    const { chatHistory, sessionContext } = options;

    const res = await fetch(`${this.ragBaseUrl}/rag/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        queryText,
        topK,
        userId,
        chatHistory: chatHistory ?? null,
        sessionContext: sessionContext ?? null,
      }),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new InternalServerErrorException(`RAG service error: ${err}`);
    }

    return res.json();
  }

  async embedOne(courseCode: string) {
    if (!this.ragBaseUrl) {
      throw new InternalServerErrorException('RAG_SERVICE_URL is not configured');
    }

    const res = await fetch(`${this.ragBaseUrl}/courses/embed-one`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ courseCode }),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new InternalServerErrorException(`RAG service error: ${err}`);
    }

    return res.json();
  }

  async embedMissing(limit = 50) {
    if (!this.ragBaseUrl) {
      throw new InternalServerErrorException('RAG_SERVICE_URL is not configured');
    }

    const res = await fetch(`${this.ragBaseUrl}/courses/embed-missing`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit }),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new InternalServerErrorException(`RAG service error: ${err}`);
    }

    return res.json();
  }

  async recommendCourses(userId: number, limit: number, authorization: string) {
    if (!this.ragBaseUrl) {
      throw new InternalServerErrorException('RAG_SERVICE_URL is not configured');
    }

    const res = await fetch(`${this.ragBaseUrl}/courses/recommend`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: authorization,
      },
      body: JSON.stringify({ userId, limit }),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new InternalServerErrorException(`RAG service error: ${err}`);
    }

    return res.json();
  }
}