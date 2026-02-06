-- raonChat: Supabase pgvector 설정
-- Supabase SQL Editor에서 실행하세요.

-- 1. pgvector 확장 활성화
create extension if not exists vector;

-- 2. 기존 테이블/함수 삭제 (재실행 시)
drop function if exists match_documents;
drop table if exists documents;

-- 3. documents 테이블 생성 (gemini-embedding-001: 3072차원)
create table documents (
    id uuid primary key default gen_random_uuid(),
    content text not null,
    embedding vector(3072),
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz default now()
);

-- 4. IVFFlat 인덱스 (cosine similarity)
-- 주의: 데이터가 최소 수백 개 이상 있어야 효과적. 초기에는 생략 가능.
create index documents_embedding_idx
    on documents
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

-- 5. match_documents RPC 함수 (cosine similarity 검색)
create or replace function match_documents(
    query_embedding vector(3072),
    match_count int default 3,
    filter jsonb default '{}'::jsonb
)
returns table (
    id uuid,
    content text,
    metadata jsonb,
    similarity float
)
language plpgsql
as $$
begin
    return query
    select
        d.id,
        d.content,
        d.metadata,
        1 - (d.embedding <=> query_embedding) as similarity
    from documents d
    where case
        when filter = '{}'::jsonb then true
        else d.metadata @> filter
    end
    order by d.embedding <=> query_embedding
    limit match_count;
end;
$$;
